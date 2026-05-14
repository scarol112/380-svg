from __future__ import annotations

import math
import re
import sys
from datetime import datetime
from pathlib import Path

from .dsl.builtins import BUILTINS, BUILTIN_RETURNS_NUMERIC, BUILTIN_RETURNS_STRING
from .dsl.lexer import tokenize
from .dsl.parser import ParseError, _ALIASES, _parse_line, _split_statements, _strip_comment
from .layout.placer import ElementPlacer
from .model import PlacedElement


_ALL_KEYWORDS = {
    "line", "rect", "wall", "door", "window", "arc", "arrow", "point",
    "label", "direction", "elementid", "dimensions", "showcornerxy",
    "color", "include", "moveto", "lineto",
    "textstyle", "textline", "textbreak", "textbox", "textappend",
    "if", "elif", "else", "for", "to", "step",
    "True", "False", "and", "or", "not",
    "string", "numeric", "tuple",
    "len", "substr", "match", "replace",
    "stop", "start",
    "vardump",
}

_RESERVED_EXPR_NAMES = frozenset({"True", "False", "and", "or", "not"})

# Matches ${name} (brace form) or $name (bare form); brace form tried first
_VARREF_RE = re.compile(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)')
_ASSIGNMENT_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*([+\-*/])?=\s*(.+)$')
_INDEX_ASSIGN_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*\[(.+?)\]\s*=\s*(.+)$')
# Tuple unpacking: two or more names on LHS (bare or parenthesized), plain = only
_UNPACK_RE = re.compile(
    r'^\(([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)+)\)\s*=\s*(.+)$'
    r'|^([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)+)\s*=\s*(.+)$'
)
_DECL_RE = re.compile(
    r'^(string|numeric|tuple)\s+'
    r'([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)'
    r'\s*(?:=\s*(.+))?$'
)
_BUILTIN_CALL_HEAD_RE = re.compile(r'\b(len|substr|match|replace)\s*\(')
_SAFE_EXPR_RE = re.compile(r'^[\d\s.+\-*/()<>=!\[\]A-Za-z_,]+$')
# (expr) inline arithmetic — bare identifiers inside are variable references
_INLINE_EXPR_RE = re.compile(r'\(([^)]*)\)')
_BARE_ID_RE = re.compile(r'[A-Za-z_][A-Za-z0-9_]*')

# Block brace detection — only match { at end of line or } at start of line
_OPEN_TRAILING_RE = re.compile(r'\{\s*$')
_CLOSE_LEADING_RE = re.compile(r'^\}\s*(.*)$')

# Control-flow header regexes (match after _strip_comment)
_FOR_HDR_RE = re.compile(
    r'^for\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s+to\s+(.+?)(?:\s+step\s+(.+?))?\s*\{\s*$',
    re.IGNORECASE,
)
_IF_HDR_RE   = re.compile(r'^if\s*\((.+)\)\s*\{\s*$', re.IGNORECASE)
# } closes previous body; elif/else opens next — all on one line
_ELIF_HDR_RE = re.compile(r'^\}\s*elif\s*\((.+)\)\s*\{\s*$', re.IGNORECASE)
_ELSE_HDR_RE = re.compile(r'^\}\s*else\s*\{\s*$', re.IGNORECASE)
_BARE_OPEN_RE = re.compile(r'^\{\s*$')


TupleVal = tuple[float | str, ...]
VarMeta  = dict[str, tuple[str, int]]   # name -> (filename, lineno of last write)


def execute_dsl(
    text: str,
    source_path: Path | None = None,
) -> list[PlacedElement]:
    vars_: dict[str, float | str | TupleVal] = {
        "__cursorx": 0.0, "__cursory": 0.0,
        "__cx": 0.0,      "__cy": 0.0,
        "__cursor": (0.0, 0.0),
        "__dir": 90.0,
        "__mltodir": 0.0,
        "__dsl_filename": "",
        "__dsl_file_lineno": 0.0,
        "__date": datetime.now().strftime("%Y-%m-%d"),
        "__stopped": 0.0,
    }
    var_meta: VarMeta = {}
    placer = ElementPlacer()
    seen: frozenset[Path] = frozenset()
    if source_path is not None:
        seen = seen | {source_path.resolve()}
    _execute_text(text, source_path, vars_, var_meta, placer, seen)
    return placer._elements


def _execute_text(
    text: str,
    source_path: Path | None,
    vars_: dict[str, float | str | TupleVal],
    var_meta: VarMeta,
    placer: ElementPlacer,
    seen: frozenset[Path],
) -> None:
    filename = source_path.name if source_path else ""
    vars_["__dsl_filename"] = filename

    lines: list[tuple[int, str]] = list(enumerate(text.splitlines(), start=1))
    _execute_block(lines, 0, len(lines), source_path, vars_, var_meta, placer, seen)


def _execute_block(
    lines: list[tuple[int, str]],
    start: int,
    end: int,
    source_path: Path | None,
    vars_: dict[str, float | str | TupleVal],
    var_meta: VarMeta,
    placer: ElementPlacer,
    seen: frozenset[Path],
) -> None:
    i = start
    while i < end:
        lineno, raw = lines[i]
        line = _strip_comment(raw)
        if not line:
            i += 1
            continue

        # When stopped, skip everything — block headers, statements, braces —
        # until a bare 'start' directive is found.
        if vars_.get("__stopped", 0.0):
            if line.split()[0].lower() == "start":
                vars_["__stopped"] = 0.0
            i += 1
            continue

        m_for = _FOR_HDR_RE.match(line)
        if m_for:
            var = m_for.group(1)
            s_expr = m_for.group(2).strip()
            e_expr = m_for.group(3).strip()
            step_expr = m_for.group(4).strip() if m_for.group(4) else "1"
            body_end = _find_matching_close(lines, i, lineno)
            body_lines = _capture_body(lines, i + 1, body_end)
            _execute_for(var, s_expr, e_expr, step_expr, body_lines,
                         lineno, source_path, vars_, var_meta, placer, seen)
            i = body_end + 1
            continue

        m_if = _IF_HDR_RE.match(line)
        if m_if:
            chain, after = _collect_if_chain(lines, i, lineno)
            for cond, b_start, b_end in chain:
                if cond is None or _eval_condition(cond, vars_, lineno):
                    _execute_block(lines, b_start, b_end, source_path, vars_, var_meta, placer, seen)
                    break
            i = after
            continue

        m_bare = _BARE_OPEN_RE.match(line)
        if m_bare:
            body_end = _find_matching_close(lines, i, lineno)
            _execute_block(lines, i + 1, body_end, source_path, vars_, var_meta, placer, seen)
            i = body_end + 1
            continue

        # Reject stray } or elif/else at top level of this block
        m_close = _CLOSE_LEADING_RE.match(line)
        if m_close:
            raise ParseError(f"Line {lineno}: unexpected '}}' (no matching opening brace)")

        for stmt in _split_statements(line):
            stmt = stmt.strip()
            if stmt:
                _execute_stmt(stmt, lineno, source_path, vars_, var_meta, placer, seen)
                if vars_.get("__stopped", 0.0):
                    break
        i += 1


def _find_matching_close(
    lines: list[tuple[int, str]],
    open_idx: int,
    open_lineno: int,
) -> int:
    """Return the index in `lines` of the closing `}` for the block opened at open_idx.

    Depth is tracked only against line-level patterns:
      open:  { as the last non-whitespace char of a stripped line
      close: } as the first non-whitespace char of a stripped line
    This avoids false matches against ${varname} or braces in quoted strings.
    """
    depth = 1
    i = open_idx + 1
    while i < len(lines):
        _, raw = lines[i]
        stripped = _strip_comment(raw)
        if not stripped:
            i += 1
            continue
        # A line may both close and open (e.g. `} else {`, `} elif (c) {`).
        # When we are looking for the *first* close at depth 0, return on the
        # close; otherwise count both so net-zero lines preserve depth.
        if _CLOSE_LEADING_RE.match(stripped):
            depth -= 1
            if depth == 0:
                return i
        if _OPEN_TRAILING_RE.search(stripped):
            depth += 1
        i += 1
    raise ParseError(f"Line {open_lineno}: unclosed '{{' — no matching '}}'")


def _capture_body(
    lines: list[tuple[int, str]],
    body_start: int,
    body_end: int,
) -> list[tuple[int, str]]:
    """Return a slice of lines from body_start up to (not including) body_end."""
    return lines[body_start:body_end]


def _collect_if_chain(
    lines: list[tuple[int, str]],
    start_idx: int,
    start_lineno: int,
) -> tuple[list[tuple[str | None, int, int]], int]:
    """Parse a full if/elif/else chain starting at start_idx.

    Returns (chain, after_idx) where chain is a list of
    (condition_str_or_None, body_start_idx, body_end_idx).
    after_idx is the index after the final closing '}'.

    `} elif` and `} else` are written as a single line: the `}` closes the
    previous body and the `elif`/`else` header opens the next one.  After
    _find_matching_close returns body_end pointing at that combined line, we
    re-examine it (i = body_end, not body_end+1) to pick up the continuation.
    """
    chain: list[tuple[str | None, int, int]] = []
    i = start_idx

    while i < len(lines):
        _, raw = lines[i]
        line = _strip_comment(raw)
        if not line:
            i += 1
            continue

        m_if   = _IF_HDR_RE.match(line)
        m_elif = _ELIF_HDR_RE.match(line)
        m_else = _ELSE_HDR_RE.match(line)

        if m_if and i == start_idx:
            cond = m_if.group(1).strip()
            body_end = _find_matching_close(lines, i, lines[i][0])
            chain.append((cond, i + 1, body_end))
            # body_end may point at "} elif" or "} else" — re-examine it
            i = body_end
        elif m_elif and chain:
            cond = m_elif.group(1).strip()
            body_end = _find_matching_close(lines, i, lines[i][0])
            chain.append((cond, i + 1, body_end))
            i = body_end
        elif m_else and chain:
            body_end = _find_matching_close(lines, i, lines[i][0])
            chain.append((None, i + 1, body_end))
            i = body_end + 1
            break
        else:
            # bare } closes the last body (no elif/else follows)
            i += 1
            break

    return chain, i


def _eval_condition(expr_text: str, vars_: dict[str, float | str | TupleVal], lineno: int) -> bool:
    expr_sub = _substitute_vars(expr_text, vars_, lineno)
    expr_sub = _evaluate_inline_exprs_bare(expr_sub, vars_, lineno)
    result = _eval_expr(expr_sub, lineno)
    return bool(result)


def _execute_for(
    var: str,
    s_expr: str,
    e_expr: str,
    step_expr: str,
    body_lines: list[tuple[int, str]],
    lineno: int,
    source_path: Path | None,
    vars_: dict[str, float | str | TupleVal],
    var_meta: VarMeta,
    placer: ElementPlacer,
    seen: frozenset[Path],
) -> None:
    start_val = _eval_expr(
        _evaluate_inline_exprs_bare(_substitute_vars(s_expr, vars_, lineno), vars_, lineno),
        lineno,
    )
    end_val = _eval_expr(
        _evaluate_inline_exprs_bare(_substitute_vars(e_expr, vars_, lineno), vars_, lineno),
        lineno,
    )
    step_val = _eval_expr(
        _evaluate_inline_exprs_bare(_substitute_vars(step_expr, vars_, lineno), vars_, lineno),
        lineno,
    )

    if step_val == 0:
        raise ParseError(f"Line {lineno}: for-loop step cannot be zero")

    raw = (end_val - start_val) / step_val
    if raw < -1e-9:
        n = 0
    else:
        n = int(math.floor(raw + 1e-9)) + 1

    if n > 100_000:
        raise ParseError(
            f"Line {lineno}: for-loop iteration count {n} exceeds limit of 100000"
        )

    for k in range(n):
        vars_[var] = start_val + k * step_val
        var_meta[var] = (str(vars_.get("__dsl_filename", "")), lineno)
        _execute_block(body_lines, 0, len(body_lines), source_path, vars_, var_meta, placer, seen)


def _execute_stmt(
    stmt: str,
    lineno: int,
    source_path: Path | None,
    vars_: dict[str, float | str | TupleVal],
    var_meta: VarMeta,
    placer: ElementPlacer,
    seen: frozenset[Path],
) -> None:
    vars_["__dsl_file_lineno"] = float(lineno)

    parts = stmt.split()
    if not parts:
        return
    first_word = parts[0].lower()
    canonical = _ALIASES.get(first_word, first_word)

    if canonical == "stop":
        vars_["__stopped"] = 1.0
        return

    if canonical == "start":
        vars_["__stopped"] = 0.0
        return

    if canonical == "include":
        tokens = tokenize(stmt, lineno)
        _execute_include(tokens, lineno, source_path, vars_, var_meta, placer, seen)
        return

    if canonical == "vardump":
        _execute_vardump(stmt, lineno, source_path, vars_, var_meta)
        return

    m_decl = _DECL_RE.match(stmt)
    if m_decl:
        _execute_declaration(m_decl, lineno, vars_, var_meta)
        return

    m_unpack = _UNPACK_RE.match(stmt)
    if m_unpack:
        _execute_unpack(m_unpack, lineno, vars_, var_meta)
        return

    m_idx = _INDEX_ASSIGN_RE.match(stmt)
    if m_idx:
        name, idx_expr, val_expr = m_idx.group(1), m_idx.group(2).strip(), m_idx.group(3).strip()
        if name.startswith('__'):
            raise ParseError(f"Line {lineno}: names starting with '__' are reserved for system variables")
        existing = vars_.get(name)
        if not isinstance(existing, tuple):
            raise ParseError(f"Line {lineno}: '{name}' is not a tuple variable")
        idx_sub = _substitute_vars(idx_expr, vars_, lineno)
        idx_sub = _evaluate_inline_exprs(idx_sub, vars_, lineno)
        idx_val = _eval_expr(idx_sub, lineno)
        if idx_val != int(idx_val) or int(idx_val) < 0:
            raise ParseError(f"Line {lineno}: tuple index must be a non-negative integer")
        idx_int = int(idx_val)
        if idx_int >= len(existing):
            raise ParseError(f"Line {lineno}: tuple index {idx_int} out of range (len={len(existing)})")
        slot_val = existing[idx_int]
        rhs_is_str = _rhs_is_string_expr(val_expr)
        if isinstance(slot_val, float) and rhs_is_str:
            raise ParseError(f"Line {lineno}: type mismatch: slot {idx_int} is numeric, got string")
        if isinstance(slot_val, str) and not rhs_is_str:
            val_ref = val_expr.strip()
            if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', val_ref):
                ref_val = vars_.get(val_ref)
                if isinstance(ref_val, float):
                    raise ParseError(f"Line {lineno}: type mismatch: slot {idx_int} is string, got numeric")
        if isinstance(slot_val, str):
            new_val: float | str = _eval_string_expr(val_expr, vars_, lineno)
        else:
            v_sub = _substitute_tuple_indexing(_substitute_vars(val_expr, vars_, lineno), vars_, lineno)
            v_sub = _evaluate_inline_exprs(v_sub, vars_, lineno)
            new_val = _eval_expr(v_sub, lineno)
        elems = list(existing)
        elems[idx_int] = new_val
        vars_[name] = tuple(elems)
        var_meta[name] = (str(vars_.get("__dsl_filename", "")), lineno)
        return

    m = _ASSIGNMENT_RE.match(stmt)
    if m:
        name, op, expr_raw = m.group(1), m.group(2), m.group(3).strip()
        if name.startswith('__'):
            raise ParseError(f"Line {lineno}: names starting with '__' are reserved for system variables")
        if name in _ALL_KEYWORDS:
            raise ParseError(f"Line {lineno}: '{name}' is a reserved keyword and cannot be assigned")
        existing = vars_.get(name)
        is_tuple_ctx = isinstance(existing, tuple) or _rhs_is_tuple_expr(expr_raw, vars_)
        if is_tuple_ctx:
            if op in ('*', '/') and not isinstance(existing, tuple):
                raise ParseError(f"Line {lineno}: '*=' and '/=' are only valid on tuple variables")
            rhs_val = _eval_tuple_expr(expr_raw, vars_, lineno)
            if op is None:
                vars_[name] = rhs_val
            elif op == '+':
                lhs = existing if isinstance(existing, tuple) else ()
                vars_[name] = _tuple_op(lhs, rhs_val, '+', lineno)
            elif op == '-':
                lhs = existing if isinstance(existing, tuple) else ()
                vars_[name] = _tuple_op(lhs, rhs_val, '-', lineno)
            elif op == '*':
                lhs = existing if isinstance(existing, tuple) else ()
                vars_[name] = _tuple_op(lhs, rhs_val, '*', lineno)
            elif op == '/':
                lhs = existing if isinstance(existing, tuple) else ()
                vars_[name] = _tuple_op(lhs, rhs_val, '/', lineno)
            var_meta[name] = (str(vars_.get("__dsl_filename", "")), lineno)
            return
        is_string_ctx = isinstance(existing, str) or _rhs_is_string_expr(expr_raw)
        if is_string_ctx:
            if op in ('-', '*', '/'):
                raise ParseError(f"Line {lineno}: '{op}=' is not defined on string variables")
            value = _eval_string_expr(expr_raw, vars_, lineno)
            if op is None:
                vars_[name] = value
            else:
                prev = existing if isinstance(existing, str) else ""
                vars_[name] = prev + value
            var_meta[name] = (str(vars_.get("__dsl_filename", "")), lineno)
            return
        if op in ('*', '/'):
            raise ParseError(f"Line {lineno}: '{op}=' is only valid on tuple variables")
        expr_sub = _substitute_tuple_indexing(_substitute_vars(expr_raw, vars_, lineno), vars_, lineno)
        expr_sub = _evaluate_inline_exprs(expr_sub, vars_, lineno)
        value = _eval_expr(expr_sub, lineno)
        if op is None:
            vars_[name] = value
        else:
            if name not in vars_:
                vars_[name] = 0.0
            if op == '+':
                vars_[name] += value  # type: ignore[operator]
            else:
                vars_[name] -= value  # type: ignore[operator]
        var_meta[name] = (str(vars_.get("__dsl_filename", "")), lineno)
        return

    sub_stmt = _substitute_vars(stmt, vars_, lineno)
    sub_stmt = _evaluate_inline_exprs(sub_stmt, vars_, lineno)
    tokens = tokenize(sub_stmt, lineno)
    if not tokens:
        return
    node = _parse_line(tokens, lineno)
    if node is not None:
        placer._dispatch(node)
        _update_system_vars(placer, vars_, var_meta)


def _execute_declaration(
    match: re.Match,
    lineno: int,
    vars_: dict[str, float | str | TupleVal],
    var_meta: VarMeta,
) -> None:
    """Handle `string`/`numeric`/`tuple` declarations (with optional initializer or multi-decl)."""
    type_name = match.group(1)
    names_str = match.group(2)
    expr_raw = match.group(3)

    names = [n.strip() for n in names_str.split(',')]
    if len(names) != len(set(names)):
        raise ParseError(f"Line {lineno}: duplicate name in multi-declaration")
    if len(names) > 1 and expr_raw is not None:
        raise ParseError(f"Line {lineno}: multi-declaration cannot have an initializer")

    for name in names:
        if name.startswith('__'):
            raise ParseError(f"Line {lineno}: names starting with '__' are reserved for system variables")
        if name in _ALL_KEYWORDS:
            raise ParseError(f"Line {lineno}: '{name}' is a reserved keyword and cannot be assigned")

    fn = str(vars_.get("__dsl_filename", ""))
    if expr_raw is None:
        if type_name == "tuple":
            for name in names:
                vars_[name] = ()
                var_meta[name] = (fn, lineno)
        else:
            default: float | str = "" if type_name == "string" else 0.0
            for name in names:
                vars_[name] = default
                var_meta[name] = (fn, lineno)
        return

    expr_raw = expr_raw.strip()
    if type_name == "string":
        vars_[names[0]] = _eval_string_expr(expr_raw, vars_, lineno)
    elif type_name == "tuple":
        vars_[names[0]] = _eval_tuple_expr(expr_raw, vars_, lineno)
    else:
        expr_sub = _substitute_tuple_indexing(_substitute_vars(expr_raw, vars_, lineno), vars_, lineno)
        expr_sub = _evaluate_inline_exprs(expr_sub, vars_, lineno)
        vars_[names[0]] = _eval_expr(expr_sub, lineno)
    var_meta[names[0]] = (fn, lineno)


def _execute_unpack(
    match: re.Match,
    lineno: int,
    vars_: dict[str, float | str | TupleVal],
    var_meta: VarMeta,
) -> None:
    # Two alternatives: parenthesized (groups 1,2) or bare (groups 3,4)
    names_str = match.group(1) if match.group(1) is not None else match.group(3)
    expr_raw = (match.group(2) if match.group(2) is not None else match.group(4)).strip()
    names = [n.strip() for n in names_str.split(',')]
    for name in names:
        if name.startswith('__'):
            raise ParseError(f"Line {lineno}: names starting with '__' are reserved for system variables")
        if name in _ALL_KEYWORDS:
            raise ParseError(f"Line {lineno}: '{name}' is a reserved keyword and cannot be assigned")
    tval = _eval_tuple_expr(expr_raw, vars_, lineno)
    if len(tval) != len(names):
        raise ParseError(
            f"Line {lineno}: unpack length mismatch — {len(names)} names but tuple has {len(tval)} elements"
        )
    fn = str(vars_.get("__dsl_filename", ""))
    for name, elem in zip(names, tval):
        vars_[name] = elem
        var_meta[name] = (fn, lineno)


def _vardump_format_value(val: float | str | TupleVal) -> str:
    if isinstance(val, tuple):
        parts = []
        for v in val:
            parts.append(f'"{v}"' if isinstance(v, str) else _fmt_float(v))
        return f"({', '.join(parts)})"
    if isinstance(val, str):
        return f'"{val}"'
    return _fmt_float(val)


def _execute_vardump(
    stmt: str,
    lineno: int,
    source_path: Path | None,
    vars_: dict[str, float | str | TupleVal],
    var_meta: VarMeta,
) -> None:
    # Parse optional filepath argument (quoted or bare word after "vardump")
    rest = stmt.split(None, 1)[1].strip() if len(stmt.split(None, 1)) > 1 else ""
    if rest.startswith('"') and rest.endswith('"') and len(rest) >= 2:
        filepath_str = rest[1:-1]
    else:
        filepath_str = rest

    # Separate system (__-prefixed) from user vars; sort each group
    sys_vars = sorted((k, v) for k, v in vars_.items() if k.startswith('__'))
    user_vars = sorted((k, v) for k, v in vars_.items() if not k.startswith('__'))

    type_code = {float: 'N', str: 'S', tuple: 'T'}
    rows: list[tuple[str, str, str, str, str]] = []
    for name, val in sys_vars + user_vars:
        tc = type_code.get(type(val), '?')
        fn, ln = var_meta.get(name, ("", 0))
        rows.append((name, tc, fn or "-", str(ln) if ln else "-", _vardump_format_value(val)))

    name_w = max((len(r[0]) for r in rows), default=4)
    name_w = max(name_w, 4)
    file_w = max((len(r[2]) for r in rows), default=4)
    file_w = max(file_w, 4)
    line_w = max((len(r[3]) for r in rows), default=4)
    line_w = max(line_w, 4)
    header = f"{'NAME':<{name_w}}  TYPE  {'FILE':<{file_w}}  {'LINE':>{line_w}}  VALUE"
    sep    = f"{'----':<{name_w}}  ----  {'----':<{file_w}}  {'----':>{line_w}}  -----"
    lines  = [header, sep] + [
        f"{r[0]:<{name_w}}  {r[1]:<4}  {r[2]:<{file_w}}  {r[3]:>{line_w}}  {r[4]}"
        for r in rows
    ]
    table  = '\n'.join(lines)

    if filepath_str:
        out_path = Path(filepath_str)
        if not out_path.is_absolute():
            base = source_path.parent if source_path else Path.cwd()
            out_path = (base / out_path).resolve()
        out_path.write_text(table + '\n')
        print(f"vardump: wrote {len(rows)} variables to {out_path}", file=sys.stderr)
    else:
        print(table, file=sys.stderr)


def _execute_include(
    tokens: list,
    lineno: int,
    source_path: Path | None,
    vars_: dict[str, float | str | TupleVal],
    var_meta: VarMeta,
    placer: ElementPlacer,
    seen: frozenset[Path],
) -> None:
    if len(tokens) < 2:
        raise ParseError(f"Line {lineno}: include requires a filename")

    raw = tokens[1].value if tokens[1].kind == "QUOTED" else " ".join(t.value for t in tokens[1:])
    inc_path = Path(raw)

    if not inc_path.is_absolute():
        base = source_path.parent if source_path else Path.cwd()
        inc_path = (base / inc_path).resolve()
    else:
        inc_path = inc_path.resolve()

    if inc_path in seen:
        raise ParseError(f"Line {lineno}: circular include detected: {inc_path}")
    if not inc_path.exists():
        raise ParseError(f"Line {lineno}: include file not found: {inc_path}")

    saved_filename = vars_["__dsl_filename"]
    _execute_text(inc_path.read_text(), inc_path, vars_, var_meta, placer, seen | {inc_path})
    vars_["__dsl_filename"] = saved_filename


def _fmt_float(val: float) -> str:
    """Format a float without scientific notation so it's safe inside eval expressions.

    %g switches to scientific notation (e.g. '3e-05') for very small or very
    large values.  The 'e' is then matched by _BARE_ID_RE as a variable name
    and corrupted.  This helper always returns a plain decimal string.
    """
    s = f"{val:.10g}"
    if 'e' in s or 'E' in s:
        s = f"{val:.10f}".rstrip('0').rstrip('.') or '0'
    return s


def _substitute_vars(text: str, vars_: dict[str, float | str | TupleVal], lineno: int) -> str:
    def replace(m: re.Match) -> str:  # type: ignore[type-arg]
        name = m.group(1) if m.group(1) is not None else m.group(2)
        val = vars_.get(name, 0.0)
        if isinstance(val, tuple):
            return ','.join(
                v if isinstance(v, str) else _fmt_float(v)
                for v in val
            )
        if isinstance(val, str):
            return val
        return _fmt_float(val)
    return _VARREF_RE.sub(replace, text)


def _evaluate_inline_exprs(text: str, vars_: dict[str, float | str | TupleVal], lineno: int) -> str:
    """Replace builtin calls and (expr) groups outside quoted strings with their values.

    Builtin calls (`len(s)`, `match(s, p)`, ...) are substituted first at any
    position. Then each remaining (expr) group is evaluated with bare
    identifiers inside resolved as variable references. Quoted strings are
    skipped throughout.
    """
    text = _substitute_tuple_indexing(text, vars_, lineno)
    text = _substitute_builtins_in_expr(text, vars_, lineno)
    result: list[str] = []
    i = 0
    in_quote = False
    while i < len(text):
        ch = text[i]
        if ch == '"':
            in_quote = not in_quote
            result.append(ch)
            i += 1
        elif ch == '(' and not in_quote:
            j = i + 1
            depth = 1
            while j < len(text) and depth > 0:
                if text[j] == '(':
                    depth += 1
                elif text[j] == ')':
                    depth -= 1
                j += 1
            if depth != 0:
                result.append(ch)
                i += 1
            else:
                inner = text[i + 1:j - 1]
                # tuple literal (x, y) — if inner has a top-level comma, emit as COORD
                if _has_top_level_comma(inner):
                    tval = _eval_tuple_expr(inner, vars_, lineno)
                    if len(tval) != 2:
                        raise ParseError(
                            f"Line {lineno}: coordinate expects 2-element tuple, got {len(tval)}"
                        )
                    result.append(','.join(
                        v if isinstance(v, str) else _fmt_float(v)
                        for v in tval
                    ))
                    i = j
                else:
                    def sub_id(m: re.Match, _v: dict = vars_, _l: int = lineno) -> str:  # type: ignore[type-arg]
                        name = m.group()
                        if name in _RESERVED_EXPR_NAMES:
                            return name
                        val = _v.get(name, 0.0)
                        if isinstance(val, str):
                            raise ParseError(f"Line {_l}: variable '{name}' is a string, not numeric")
                        if isinstance(val, tuple):
                            raise ParseError(f"Line {_l}: variable '{name}' is a tuple, not numeric")
                        return _fmt_float(val)
                    expr = _BARE_ID_RE.sub(sub_id, inner)
                    result.append(_fmt_float(_eval_expr(expr, lineno)))
                    i = j
        else:
            result.append(ch)
            i += 1
    return ''.join(result)


def _evaluate_inline_exprs_bare(text: str, vars_: dict[str, float | str | TupleVal], lineno: int) -> str:
    """Like _evaluate_inline_exprs but also substitutes bare identifiers at the top level.

    Used for evaluating condition expressions and for/step bounds that are not
    wrapped in parentheses.
    """
    text = _substitute_tuple_indexing(text, vars_, lineno)
    text = _substitute_builtins_in_expr(text, vars_, lineno)
    def sub_id(m: re.Match, _v: dict = vars_, _l: int = lineno) -> str:  # type: ignore[type-arg]
        name = m.group()
        if name in _RESERVED_EXPR_NAMES:
            return name
        val = _v.get(name, 0.0)
        if isinstance(val, str):
            raise ParseError(f"Line {_l}: variable '{name}' is a string, not numeric")
        if isinstance(val, tuple):
            raise ParseError(f"Line {_l}: variable '{name}' is a tuple, not numeric")
        return _fmt_float(val)
    return _BARE_ID_RE.sub(sub_id, text)


def _parse_call_args(
    text: str,
    paren_pos: int,
    vars_: dict[str, float | str | TupleVal],
    lineno: int,
) -> tuple[list[object], int]:
    """Parse a comma-separated argument list starting at the `(` at paren_pos.

    Returns (args, position_after_closing_paren). Each arg is one of:
      - quoted string literal ("..." or '...')
      - bare identifier resolved against `vars_` (may yield str or float)
      - numeric literal
      - nested builtin call (resolved recursively)
    Compound numeric expressions (e.g. `x + 1`) are NOT supported as args.
    """
    if paren_pos >= len(text) or text[paren_pos] != '(':
        raise ParseError(f"Line {lineno}: expected '(' in function call")
    i = paren_pos + 1
    n = len(text)
    args: list[object] = []

    # Skip whitespace; handle empty arg list
    while i < n and text[i].isspace():
        i += 1
    if i < n and text[i] == ')':
        return args, i + 1

    while i < n:
        while i < n and text[i].isspace():
            i += 1
        if i >= n:
            break

        ch = text[i]
        if ch in ('"', "'"):
            quote = ch
            j = i + 1
            while j < n and text[j] != quote:
                j += 1
            if j >= n:
                raise ParseError(f"Line {lineno}: unterminated string in argument list")
            args.append(text[i + 1:j].replace('\\n', '\n'))
            i = j + 1
        elif ch.isalpha() or ch == '_':
            j = i
            while j < n and (text[j].isalnum() or text[j] == '_'):
                j += 1
            name = text[i:j]
            k = j
            while k < n and text[k].isspace():
                k += 1
            if k < n and text[k] == '(':
                if name not in BUILTINS:
                    raise ParseError(f"Line {lineno}: unknown function {name!r}")
                inner_args, end = _parse_call_args(text, k, vars_, lineno)
                args.append(BUILTINS[name](inner_args, lineno))
                i = end
            else:
                args.append(vars_.get(name, 0.0))
                i = j
        elif ch == '-' or ch.isdigit() or ch == '.':
            j = i
            if text[j] == '-':
                j += 1
            saw_digit = False
            while j < n and (text[j].isdigit() or text[j] == '.'):
                if text[j].isdigit():
                    saw_digit = True
                j += 1
            if not saw_digit:
                raise ParseError(f"Line {lineno}: malformed number in argument list")
            args.append(float(text[i:j]))
            i = j
        else:
            raise ParseError(f"Line {lineno}: unexpected character {ch!r} in argument list")

        while i < n and text[i].isspace():
            i += 1
        if i < n and text[i] == ',':
            i += 1
            continue
        if i < n and text[i] == ')':
            return args, i + 1
        raise ParseError(f"Line {lineno}: expected ',' or ')' in argument list")

    raise ParseError(f"Line {lineno}: unterminated function call")


def _substitute_builtins_in_expr(
    text: str,
    vars_: dict[str, float | str | TupleVal],
    lineno: int,
) -> str:
    """Replace numeric-returning builtin calls with their decimal value.

    Walks `text` skipping content inside "..." and '...' string literals.
    `substr`/`replace` (string-returning) raise ParseError — they're only valid
    in string-expression context.
    """
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in ('"', "'"):
            quote = ch
            out.append(ch)
            i += 1
            while i < n and text[i] != quote:
                out.append(text[i])
                i += 1
            if i < n:
                out.append(text[i])
                i += 1
            continue
        m = _BUILTIN_CALL_HEAD_RE.match(text, i)
        if m and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == '_')):
            name = m.group(1)
            paren_pos = m.end() - 1
            args, after = _parse_call_args(text, paren_pos, vars_, lineno)
            if name in BUILTIN_RETURNS_STRING:
                raise ParseError(
                    f"Line {lineno}: {name}() returns a string and is not valid in a numeric expression"
                )
            result = BUILTINS[name](args, lineno)
            out.append(_fmt_float(float(result)))
            i = after
            continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _eval_string_expr(
    text: str,
    vars_: dict[str, float | str | TupleVal],
    lineno: int,
) -> str:
    """Evaluate a string expression: terms joined by `+`.

    Each term is: a quoted literal, a bare variable reference (must be string),
    a ${name}/$name reference, or a string-returning builtin call. Numeric
    terms (literals, numeric vars, len/match results) raise ParseError — there
    is no implicit numeric-to-string coercion.
    """
    # Pre-substitute tuple indexing so name[i] yields the slot's string value
    text = _substitute_tuple_indexing(text, vars_, lineno)
    parts: list[str] = []
    i = 0
    n = len(text)
    expect_term = True

    def lookup_str(name: str) -> str:
        val = vars_.get(name)
        if val is None:
            return ""
        if isinstance(val, str):
            return val
        raise ParseError(
            f"Line {lineno}: cannot use numeric variable {name!r} in a string expression"
        )

    while i < n:
        if text[i].isspace():
            i += 1
            continue
        if expect_term:
            ch = text[i]
            if ch in ('"', "'"):
                quote = ch
                j = i + 1
                while j < n and text[j] != quote:
                    j += 1
                if j >= n:
                    raise ParseError(f"Line {lineno}: unterminated string literal")
                parts.append(text[i + 1:j].replace('\\n', '\n'))
                i = j + 1
                expect_term = False
            elif ch == '$':
                j = i + 1
                if j < n and text[j] == '{':
                    j += 1
                    start = j
                    while j < n and text[j] != '}':
                        j += 1
                    if j >= n:
                        raise ParseError(f"Line {lineno}: unterminated ${{...}} reference")
                    name = text[start:j]
                    j += 1
                else:
                    start = j
                    while j < n and (text[j].isalnum() or text[j] == '_'):
                        j += 1
                    name = text[start:j]
                if not name:
                    raise ParseError(f"Line {lineno}: empty variable reference")
                parts.append(lookup_str(name))
                i = j
                expect_term = False
            elif ch.isalpha() or ch == '_':
                j = i
                while j < n and (text[j].isalnum() or text[j] == '_'):
                    j += 1
                name = text[i:j]
                k = j
                while k < n and text[k].isspace():
                    k += 1
                if k < n and text[k] == '(':
                    if name not in BUILTINS:
                        raise ParseError(f"Line {lineno}: unknown function {name!r}")
                    args, end = _parse_call_args(text, k, vars_, lineno)
                    if name in BUILTIN_RETURNS_NUMERIC:
                        raise ParseError(
                            f"Line {lineno}: {name}() returns a numeric value, cannot be used in a string expression"
                        )
                    parts.append(BUILTINS[name](args, lineno))
                    i = end
                else:
                    parts.append(lookup_str(name))
                    i = j
                expect_term = False
            else:
                raise ParseError(f"Line {lineno}: unexpected character {ch!r} in string expression")
        else:
            if text[i] == '+':
                expect_term = True
                i += 1
            else:
                raise ParseError(f"Line {lineno}: expected '+' in string expression, got {text[i]!r}")
    if expect_term:
        raise ParseError(f"Line {lineno}: string expression is incomplete")
    return ''.join(parts)


def _rhs_is_string_expr(text: str) -> bool:
    """Quick check: does the RHS start with a string literal?

    Used to dispatch plain `name = expr` assignments when the LHS is not
    already-typed as a string variable.
    """
    stripped = text.lstrip()
    return bool(stripped) and stripped[0] in ('"', "'")


def _has_top_level_comma(text: str) -> bool:
    """True if `text` contains a comma at paren/bracket depth 0, outside quotes."""
    depth = 0
    in_quote = False
    for ch in text:
        if ch == '"':
            in_quote = not in_quote
        elif not in_quote:
            if ch in ('(', '['):
                depth += 1
            elif ch in (')', ']'):
                depth -= 1
            elif ch == ',' and depth == 0:
                return True
    return False


def _rhs_is_tuple_expr(text: str, vars_: dict[str, float | str | TupleVal]) -> bool:
    """Heuristic: does the RHS look like a tuple expression?"""
    stripped = text.strip()
    if _has_top_level_comma(stripped):
        return True
    if stripped.startswith('(') and stripped.endswith(')'):
        inner = stripped[1:-1]
        if _has_top_level_comma(inner):
            return True
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', stripped):
        return isinstance(vars_.get(stripped), tuple)
    # $name or ${name} reference
    m_ref = re.fullmatch(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)', stripped)
    if m_ref:
        name = m_ref.group(1) if m_ref.group(1) is not None else m_ref.group(2)
        return isinstance(vars_.get(name), tuple)
    # op form: operand OP operand where an operand is a tuple var
    m = re.fullmatch(
        r'([A-Za-z_][A-Za-z0-9_]*|\(.+\))\s*[+\-*/]\s*([A-Za-z_][A-Za-z0-9_]*|\(.+\))',
        stripped,
    )
    if m:
        left = m.group(1).strip()
        right = m.group(2).strip()
        return isinstance(vars_.get(left), tuple) or isinstance(vars_.get(right), tuple)
    return False


def _eval_tuple_expr(
    text: str,
    vars_: dict[str, float | str | TupleVal],
    lineno: int,
) -> TupleVal:
    """Evaluate a tuple expression and return a TupleVal."""
    text = text.strip()

    # Operation form: find top-level +/-/*/÷ with at least one tuple operand
    op_char, left_s, right_s = _split_top_level_op(text)
    if op_char is not None:
        left_val = _resolve_tuple_operand(left_s, vars_, lineno)
        right_val = _resolve_tuple_operand(right_s, vars_, lineno)
        if isinstance(left_val, tuple) or isinstance(right_val, tuple):
            if isinstance(left_val, tuple) and not isinstance(right_val, tuple):
                # scalar broadcast: replicate scalar to match lhs length
                rhs: TupleVal = tuple(right_val for _ in left_val)  # type: ignore[misc]
                lhs: TupleVal = left_val
            elif isinstance(right_val, tuple) and not isinstance(left_val, tuple):
                lhs = tuple(left_val for _ in right_val)  # type: ignore[misc]
                rhs = right_val
            else:
                lhs = left_val  # type: ignore[assignment]
                rhs = right_val  # type: ignore[assignment]
            return _tuple_op(lhs, rhs, op_char, lineno)
        # neither side is a tuple — fall through

    # Parenthesized list with top-level comma
    if text.startswith('(') and text.endswith(')'):
        inner = text[1:-1]
        if _has_top_level_comma(inner):
            return _eval_tuple_literal(inner, vars_, lineno)

    # Bare-tuple literal (top-level comma)
    if _has_top_level_comma(text):
        return _eval_tuple_literal(text, vars_, lineno)

    # Bare variable reference resolving to a tuple
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', text):
        val = vars_.get(text)
        if isinstance(val, tuple):
            return val

    # $varname or ${varname} reference resolving to a tuple
    m_ref = re.fullmatch(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)', text)
    if m_ref:
        name = m_ref.group(1) if m_ref.group(1) is not None else m_ref.group(2)
        val = vars_.get(name)
        if isinstance(val, tuple):
            return val

    # Single scalar — wrap in 1-tuple
    scalar = _eval_scalar_element(text, vars_, lineno)
    return (scalar,)


def _resolve_tuple_operand(
    text: str,
    vars_: dict[str, float | str | TupleVal],
    lineno: int,
) -> float | str | TupleVal:
    """Resolve one side of a tuple op: tuple var, scalar var, or literal."""
    t = text.strip()
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', t):
        val = vars_.get(t)
        if val is not None:
            return val
    m_ref = re.fullmatch(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)', t)
    if m_ref:
        name = m_ref.group(1) if m_ref.group(1) is not None else m_ref.group(2)
        val = vars_.get(name)
        if val is not None:
            return val
    if t.startswith('(') and t.endswith(')'):
        inner = t[1:-1]
        if _has_top_level_comma(inner):
            return _eval_tuple_literal(inner, vars_, lineno)
    if _has_top_level_comma(t):
        return _eval_tuple_literal(t, vars_, lineno)
    return _eval_scalar_element(t, vars_, lineno)


def _eval_tuple_literal(text: str, vars_: dict[str, float | str | TupleVal], lineno: int) -> TupleVal:
    """Split on top-level commas and evaluate each element as a scalar."""
    parts: list[str] = []
    depth = 0
    in_quote = False
    current: list[str] = []
    for ch in text:
        if ch == '"':
            in_quote = not in_quote
            current.append(ch)
        elif not in_quote:
            if ch in ('(', '['):
                depth += 1
                current.append(ch)
            elif ch in (')', ']'):
                depth -= 1
                current.append(ch)
            elif ch == ',' and depth == 0:
                parts.append(''.join(current).strip())
                current = []
            else:
                current.append(ch)
        else:
            current.append(ch)
    parts.append(''.join(current).strip())
    return tuple(_eval_scalar_element(p, vars_, lineno) for p in parts)


def _eval_scalar_element(
    text: str,
    vars_: dict[str, float | str | TupleVal],
    lineno: int,
) -> float | str:
    """Evaluate a single element of a tuple literal as either string or numeric."""
    t = text.strip()
    if t.startswith('"') or t.startswith("'"):
        return _eval_string_expr(t, vars_, lineno)
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', t):
        val = vars_.get(t)
        if isinstance(val, str):
            return val
        if isinstance(val, float) or isinstance(val, int):
            return float(val)
        if val is None:
            return 0.0
    expr_sub = _substitute_tuple_indexing(_substitute_vars(t, vars_, lineno), vars_, lineno)
    expr_sub = _evaluate_inline_exprs(expr_sub, vars_, lineno)
    return _eval_expr(expr_sub, lineno)


def _split_top_level_op(text: str) -> tuple[str | None, str, str]:
    """Find the last top-level +/-/*/÷ (outside parens/quotes) and split around it.

    Returns (op, left, right) or (None, '', '') if none found.
    Searches right-to-left so `a + b + c` splits as `(a + b) + c`.
    Addition/subtraction are lower precedence — scan them after mul/div.
    """
    # Scan right-to-left for +/- first (lower precedence), then */÷
    for ops in ('+', '-', '*', '/'):
        depth = 0
        in_quote = False
        for i in range(len(text) - 1, -1, -1):
            ch = text[i]
            if ch == '"':
                in_quote = not in_quote
            elif not in_quote:
                if ch in (')', ']'):
                    depth += 1
                elif ch in ('(', '['):
                    depth -= 1
                elif ch == ops and depth == 0 and i > 0:
                    return ops, text[:i].strip(), text[i + 1:].strip()
    return None, '', ''


def _tuple_op(
    a: TupleVal,
    b: TupleVal,
    op: str,
    lineno: int,
) -> TupleVal:
    """Apply element-wise op to two tuples. Result length = min(len(a), len(b))."""
    n = min(len(a), len(b))
    result: list[float | str] = []
    for i in range(n):
        va, vb = a[i], b[i]
        if isinstance(va, str) and isinstance(vb, str):
            if op != '+':
                raise ParseError(f"Line {lineno}: '{op}' is not defined on string tuple slots")
            result.append(va + vb)
        elif isinstance(va, float) and isinstance(vb, float):
            if op == '+':
                result.append(va + vb)
            elif op == '-':
                result.append(va - vb)
            elif op == '*':
                result.append(va * vb)
            elif op == '/':
                if vb == 0:
                    raise ParseError(f"Line {lineno}: division by zero in tuple op")
                result.append(va / vb)
        else:
            raise ParseError(
                f"Line {lineno}: type mismatch in tuple op at slot {i}: "
                f"{'string' if isinstance(va, str) else 'numeric'} vs "
                f"{'string' if isinstance(vb, str) else 'numeric'}"
            )
    return tuple(result)


# Matches name[expr] outside quoted strings — used for tuple index substitution
_TUPLE_INDEX_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\[([^\]]+)\]')


def _substitute_tuple_indexing(
    text: str,
    vars_: dict[str, float | str | TupleVal],
    lineno: int,
) -> str:
    """Replace name[expr] patterns with the tuple slot value."""
    if '[' not in text:
        return text
    result: list[str] = []
    i = 0
    n = len(text)
    in_quote = False
    while i < n:
        ch = text[i]
        if ch == '"':
            in_quote = not in_quote
            result.append(ch)
            i += 1
            continue
        if in_quote:
            result.append(ch)
            i += 1
            continue
        m = _TUPLE_INDEX_RE.match(text, i)
        if m:
            name = m.group(1)
            idx_expr = m.group(2).strip()
            val = vars_.get(name)
            if isinstance(val, tuple):
                idx_sub = _substitute_vars(idx_expr, vars_, lineno)
                idx_sub = _evaluate_inline_exprs(idx_sub, vars_, lineno)
                idx_float = _eval_expr(idx_sub, lineno)
                if idx_float != int(idx_float) or int(idx_float) < 0:
                    raise ParseError(f"Line {lineno}: tuple index must be a non-negative integer")
                idx_int = int(idx_float)
                if idx_int >= len(val):
                    raise ParseError(
                        f"Line {lineno}: tuple index {idx_int} out of range (len={len(val)})"
                    )
                slot = val[idx_int]
                result.append(slot if isinstance(slot, str) else _fmt_float(slot))
                i = m.end()
                continue
        result.append(ch)
        i += 1
    return ''.join(result)


def _eval_expr(expr: str, lineno: int) -> float:
    if not _SAFE_EXPR_RE.match(expr):
        raise ParseError(f"Line {lineno}: invalid expression: {expr!r}")
    try:
        result = eval(expr, {"__builtins__": {}, "True": True, "False": False}, {})
        return float(result)
    except ZeroDivisionError:
        raise ParseError(f"Line {lineno}: division by zero in: {expr!r}")
    except Exception as e:
        raise ParseError(f"Line {lineno}: expression error in {expr!r}: {e}")


def _update_system_vars(
    placer: ElementPlacer,
    vars_: dict[str, float | str | TupleVal],
    var_meta: VarMeta,
) -> None:
    ox, oy = placer._canvas_origin
    cx = placer._cursor.x - ox
    cy = placer._cursor.y - oy
    fn = str(vars_.get("__dsl_filename", ""))
    ln = int(vars_.get("__dsl_file_lineno", 0))
    vars_["__cursorx"] = cx;  var_meta["__cursorx"] = (fn, ln)
    vars_["__cursory"] = cy;  var_meta["__cursory"] = (fn, ln)
    vars_["__cx"]      = cx;  var_meta["__cx"]      = (fn, ln)
    vars_["__cy"]      = cy;  var_meta["__cy"]      = (fn, ln)
    vars_["__cursor"]  = (cx, cy); var_meta["__cursor"] = (fn, ln)
    vars_["__dir"]     = placer._cursor.direction; var_meta["__dir"] = (fn, ln)
    vars_["__mltodir"] = placer._mltodir;          var_meta["__mltodir"] = (fn, ln)
