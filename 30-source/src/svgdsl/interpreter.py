from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass
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
    "vardump", "vartrace",
    "def", "return",
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
_SAFE_COND_RE = re.compile(r"^[\d\s.+\-*/()<>=!\[\]A-Za-z_,'\"\\.]+$")
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

# Function definition / call regexes
_DEF_HDR_RE   = re.compile(r'^def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\)\s*\{\s*$')
_RETURN_RE    = re.compile(r'^return\b\s*(.*)$')
# Anchored form for statement-start detection
_CALL_STMT_RE = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*\(')
# Unanchored form for scanning inside expressions (used with .match(text, pos))
_CALL_EXPR_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*\(')


@dataclass(frozen=True)
class _FuncDef:
    name: str
    params: tuple[str, ...]
    body: list[tuple[int, str]]
    def_file: str
    def_lineno: int


class _ReturnSignal(Exception):
    __slots__ = ("value",)
    def __init__(self, value: object) -> None:
        self.value = value


TupleVal = tuple[float | str, ...]
VarMeta  = dict[str, tuple[str, int]]   # name -> (filename, lineno of last write)


class _Trace:
    __slots__ = ("active", "watch", "log", "filepath", "last_loc")

    def __init__(self) -> None:
        self.active: bool = False
        self.watch: set[str] | None = None  # None = all variables
        self.log: list[tuple[str, str, str, int, str]] = []  # (name,type,file,line,value_str)
        self.filepath: str | None = None
        self.last_loc: tuple[str, int] | None = None  # (filename, lineno) of last live line


_current_trace: _Trace | None = None


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
    funcs: dict[str, _FuncDef] = {}
    depth: list[int] = [0]
    global _current_trace
    _current_trace = _Trace()
    placer = ElementPlacer()
    seen: frozenset[Path] = frozenset()
    if source_path is not None:
        seen = seen | {source_path.resolve()}
    # Each DSL recursion level uses ~10 Python frames; raise limit to support 256 levels
    old_limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old_limit, 256 * 12 + 500))
    try:
        _execute_text(text, source_path, vars_, var_meta, funcs, depth, placer, seen)
    except _ReturnSignal:
        raise ParseError("'return' outside function")
    finally:
        sys.setrecursionlimit(old_limit)
    _print_trace_summary(_current_trace, source_path)
    _current_trace = None
    return placer._elements


def _execute_text(
    text: str,
    source_path: Path | None,
    vars_: dict[str, float | str | TupleVal],
    var_meta: VarMeta,
    funcs: dict[str, _FuncDef],
    depth: list[int],
    placer: ElementPlacer,
    seen: frozenset[Path],
    locals_: dict[str, float | str | TupleVal] | None = None,
) -> None:
    filename = source_path.name if source_path else ""
    vars_["__dsl_filename"] = filename

    lines: list[tuple[int, str]] = list(enumerate(text.splitlines(), start=1))
    _execute_block(lines, 0, len(lines), source_path, vars_, var_meta, funcs, depth, placer, seen, locals_)


def _execute_block(
    lines: list[tuple[int, str]],
    start: int,
    end: int,
    source_path: Path | None,
    vars_: dict[str, float | str | TupleVal],
    var_meta: VarMeta,
    funcs: dict[str, _FuncDef],
    depth: list[int],
    placer: ElementPlacer,
    seen: frozenset[Path],
    locals_: dict[str, float | str | TupleVal] | None = None,
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

        m_def = _DEF_HDR_RE.match(line)
        if m_def:
            fname = m_def.group(1)
            params_raw = m_def.group(2).strip()
            if fname in _ALL_KEYWORDS:
                raise ParseError(f"Line {lineno}: '{fname}' is a reserved keyword and cannot be used as a function name")
            if fname in BUILTINS:
                raise ParseError(f"Line {lineno}: '{fname}' is a builtin and cannot be redefined")
            if fname.startswith('__'):
                raise ParseError(f"Line {lineno}: names starting with '__' are reserved for system variables")
            params: tuple[str, ...] = ()
            if params_raw:
                raw_params = [p.strip() for p in params_raw.split(',')]
                for p in raw_params:
                    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', p):
                        raise ParseError(f"Line {lineno}: invalid parameter name {p!r}")
                    if p.startswith('__'):
                        raise ParseError(f"Line {lineno}: parameter name {p!r} cannot start with '__'")
                if len(raw_params) != len(set(raw_params)):
                    raise ParseError(f"Line {lineno}: duplicate parameter name in function {fname!r}")
                params = tuple(raw_params)
            body_end = _find_matching_close(lines, i, lineno)
            body_lines = _capture_body(lines, i + 1, body_end)
            fn_file = str(vars_.get("__dsl_filename", ""))
            funcs[fname] = _FuncDef(name=fname, params=params, body=body_lines,
                                    def_file=fn_file, def_lineno=lineno)
            i = body_end + 1
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
                         lineno, source_path, vars_, var_meta, funcs, depth, placer, seen, locals_)
            i = body_end + 1
            continue

        m_if = _IF_HDR_RE.match(line)
        if m_if:
            chain, after = _collect_if_chain(lines, i, lineno)
            for cond, b_start, b_end in chain:
                if cond is None or _eval_condition(cond, vars_, funcs, depth, locals_, lineno,
                                                    source_path, var_meta, placer, seen):
                    _execute_block(lines, b_start, b_end, source_path, vars_, var_meta, funcs, depth, placer, seen, locals_)
                    break
            i = after
            continue

        m_bare = _BARE_OPEN_RE.match(line)
        if m_bare:
            body_end = _find_matching_close(lines, i, lineno)
            _execute_block(lines, i + 1, body_end, source_path, vars_, var_meta, funcs, depth, placer, seen, locals_)
            i = body_end + 1
            continue

        # Reject stray } or elif/else at top level of this block
        m_close = _CLOSE_LEADING_RE.match(line)
        if m_close:
            raise ParseError(f"Line {lineno}: unexpected '}}' (no matching opening brace)")

        for stmt in _split_statements(line):
            stmt = stmt.strip()
            if stmt:
                _execute_stmt(stmt, lineno, source_path, vars_, var_meta, funcs, depth, placer, seen, locals_)
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


def _effective_vars(
    vars_: dict[str, float | str | TupleVal],
    locals_: dict[str, float | str | TupleVal] | None,
) -> dict[str, float | str | TupleVal]:
    """Return a merged view of globals + locals for read-only lookups.

    Locals shadow globals for user names; system vars (__-prefixed) always
    come from globals regardless.  Returns a new dict — do not mutate it.
    """
    if locals_ is None:
        return vars_
    merged = dict(vars_)
    merged.update(locals_)
    return merged


def _write(
    name: str,
    value: float | str | TupleVal,
    vars_: dict[str, float | str | TupleVal],
    locals_: dict[str, float | str | TupleVal] | None,
    var_meta: VarMeta,
    lineno: int,
) -> None:
    """Write `name = value` to the correct scope.

    System vars (__-prefixed) always go to globals.  User vars go to locals
    when inside a function (locals_ is not None), else to globals.
    """
    fn = str(vars_.get("__dsl_filename", ""))
    if name.startswith('__') or locals_ is None:
        vars_[name] = value
        var_meta[name] = (fn, lineno)
    else:
        locals_[name] = value
        # Keep var_meta in globals for vardump/vartrace — record last write location
        var_meta[name] = (fn, lineno)


def _invoke_function(
    fn: _FuncDef,
    args: list[object],
    lineno: int,
    source_path: Path | None,
    vars_: dict[str, float | str | TupleVal],
    var_meta: VarMeta,
    funcs: dict[str, _FuncDef],
    depth: list[int],
    placer: object,
    seen: frozenset[Path],
) -> float | str | TupleVal:
    """Execute a user-defined function and return its value.

    Validates arity, builds a fresh locals dict, and runs the captured body
    inside _execute_block.  _ReturnSignal unwinds the call; fall-off yields 0.0.
    """
    if len(args) != len(fn.params):
        raise ParseError(
            f"Line {lineno}: function {fn.name!r} expects {len(fn.params)} argument(s), got {len(args)}"
        )
    depth[0] += 1
    if depth[0] > 256:
        depth[0] -= 1
        raise ParseError(
            f"Line {lineno}: maximum recursion depth (256) exceeded in call to {fn.name!r}"
        )
    new_locals: dict[str, float | str | TupleVal] = {}
    for pname, aval in zip(fn.params, args):
        if isinstance(aval, (float, int)):
            new_locals[pname] = float(aval)
        else:
            new_locals[pname] = aval  # type: ignore[assignment]
    # Placer may be None when called from expression context; create a throwaway
    from .layout.placer import ElementPlacer as _EP
    eff_placer = placer if placer is not None else _EP()
    try:
        _execute_block(
            fn.body, 0, len(fn.body),
            source_path, vars_, var_meta, funcs, depth,
            eff_placer, seen, new_locals,  # type: ignore[arg-type]
        )
        return 0.0
    except _ReturnSignal as sig:
        return sig.value
    finally:
        depth[0] -= 1


def _eval_condition(
    expr_text: str,
    vars_: dict[str, float | str | TupleVal],
    funcs: dict[str, _FuncDef],
    depth: list[int],
    locals_: dict[str, float | str | TupleVal] | None,
    lineno: int,
    source_path: Path | None = None,
    var_meta: VarMeta | None = None,
    placer: object = None,
    seen: frozenset[Path] | None = None,
) -> bool:
    eff = _effective_vars(vars_, locals_)

    def _sub_typed(m: re.Match) -> str:  # type: ignore[type-arg]
        name = m.group(1) if m.group(1) is not None else m.group(2)
        val = eff.get(name, 0.0)
        if isinstance(val, str):
            return repr(val)   # becomes 'letter' — a Python string literal
        if isinstance(val, tuple):
            return '0'
        return _fmt_float(val)

    expr_sub = _VARREF_RE.sub(_sub_typed, expr_text)
    expr_sub = _evaluate_inline_exprs_bare(expr_sub, vars_, funcs, depth, locals_, lineno,
                                           source_path, var_meta, placer, seen)
    if '__' in expr_sub:
        raise ParseError(f"Line {lineno}: invalid condition: {expr_sub!r}")
    if not _SAFE_COND_RE.match(expr_sub):
        raise ParseError(f"Line {lineno}: invalid condition: {expr_sub!r}")
    try:
        result = eval(expr_sub, {"__builtins__": {}, "True": True, "False": False}, {})
        return bool(result)
    except ZeroDivisionError:
        raise ParseError(f"Line {lineno}: division by zero in condition: {expr_sub!r}")
    except Exception as e:
        raise ParseError(f"Line {lineno}: condition error in {expr_sub!r}: {e}")


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
    funcs: dict[str, _FuncDef],
    depth: list[int],
    placer: ElementPlacer,
    seen: frozenset[Path],
    locals_: dict[str, float | str | TupleVal] | None = None,
) -> None:
    eff = _effective_vars(vars_, locals_)
    start_val = _eval_expr(
        _evaluate_inline_exprs_bare(_substitute_vars(s_expr, eff, lineno), vars_, funcs, depth, locals_, lineno,
                                    source_path, var_meta, placer, seen),
        lineno,
    )
    end_val = _eval_expr(
        _evaluate_inline_exprs_bare(_substitute_vars(e_expr, eff, lineno), vars_, funcs, depth, locals_, lineno,
                                    source_path, var_meta, placer, seen),
        lineno,
    )
    step_val = _eval_expr(
        _evaluate_inline_exprs_bare(_substitute_vars(step_expr, eff, lineno), vars_, funcs, depth, locals_, lineno,
                                    source_path, var_meta, placer, seen),
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
        # for-loop variable: write to locals if inside function, else globals
        _write(var, start_val + k * step_val, vars_, locals_, var_meta, lineno)
        _maybe_trace(var, vars_, var_meta)
        _execute_block(body_lines, 0, len(body_lines), source_path, vars_, var_meta, funcs, depth, placer, seen, locals_)


def _execute_stmt(
    stmt: str,
    lineno: int,
    source_path: Path | None,
    vars_: dict[str, float | str | TupleVal],
    var_meta: VarMeta,
    funcs: dict[str, _FuncDef],
    depth: list[int],
    placer: ElementPlacer,
    seen: frozenset[Path],
    locals_: dict[str, float | str | TupleVal] | None = None,
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
        _execute_include(tokens, lineno, source_path, vars_, var_meta, funcs, depth, placer, seen, locals_)
        return

    if canonical == "vardump":
        _execute_vardump(stmt, lineno, source_path, vars_, var_meta)
        return

    if canonical == "vartrace":
        _execute_vartrace(stmt, lineno, source_path)
        return

    # return statement — only valid inside a function (_ReturnSignal unwinds)
    m_ret = _RETURN_RE.match(stmt)
    if m_ret:
        expr_raw = m_ret.group(1).strip()
        if not expr_raw:
            raise _ReturnSignal(0.0)
        eff = _effective_vars(vars_, locals_)
        # Detect return type: tuple, string, or numeric
        if _rhs_is_tuple_expr(expr_raw, eff):
            raise _ReturnSignal(_eval_tuple_expr(expr_raw, eff, lineno, funcs, depth, locals_,
                                                 source_path, var_meta, placer, seen))
        if _rhs_is_string_expr(expr_raw, eff):
            raise _ReturnSignal(_eval_string_expr(expr_raw, eff, lineno, funcs, depth, locals_,
                                                  source_path, var_meta, placer, seen))
        expr_sub = _substitute_tuple_indexing(_substitute_vars(expr_raw, eff, lineno), eff, lineno)
        expr_sub = _evaluate_inline_exprs(expr_sub, vars_, funcs, depth, locals_, lineno,
                                          source_path, var_meta, placer, seen)
        raise _ReturnSignal(_eval_expr(expr_sub, lineno))

    m_decl = _DECL_RE.match(stmt)
    if m_decl:
        _execute_declaration(m_decl, lineno, vars_, var_meta, funcs, depth, locals_,
                             source_path, placer, seen)
        return

    m_unpack = _UNPACK_RE.match(stmt)
    if m_unpack:
        _execute_unpack(m_unpack, lineno, vars_, var_meta, funcs, depth, locals_,
                        source_path, placer, seen)
        return

    m_idx = _INDEX_ASSIGN_RE.match(stmt)
    if m_idx:
        name, idx_expr, val_expr = m_idx.group(1), m_idx.group(2).strip(), m_idx.group(3).strip()
        if name.startswith('__'):
            raise ParseError(f"Line {lineno}: names starting with '__' are reserved for system variables")
        eff = _effective_vars(vars_, locals_)
        existing = eff.get(name)
        if not isinstance(existing, tuple):
            raise ParseError(f"Line {lineno}: '{name}' is not a tuple variable")
        idx_sub = _substitute_vars(idx_expr, eff, lineno)
        idx_sub = _evaluate_inline_exprs(idx_sub, vars_, funcs, depth, locals_, lineno,
                                         source_path, var_meta, placer, seen)
        idx_val = _eval_expr(idx_sub, lineno)
        if idx_val != int(idx_val) or int(idx_val) < 0:
            raise ParseError(f"Line {lineno}: tuple index must be a non-negative integer")
        idx_int = int(idx_val)
        if idx_int >= len(existing):
            raise ParseError(f"Line {lineno}: tuple index {idx_int} out of range (len={len(existing)})")
        slot_val = existing[idx_int]
        rhs_is_str = _rhs_is_string_expr(val_expr, eff)
        if isinstance(slot_val, float) and rhs_is_str:
            raise ParseError(f"Line {lineno}: type mismatch: slot {idx_int} is numeric, got string")
        if isinstance(slot_val, str) and not rhs_is_str:
            val_ref = val_expr.strip()
            if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', val_ref):
                ref_val = eff.get(val_ref)
                if isinstance(ref_val, float):
                    raise ParseError(f"Line {lineno}: type mismatch: slot {idx_int} is string, got numeric")
        if isinstance(slot_val, str):
            new_val: float | str = _eval_string_expr(val_expr, eff, lineno, funcs, depth, locals_,
                                                      source_path, var_meta, placer, seen)
        else:
            v_sub = _substitute_tuple_indexing(_substitute_vars(val_expr, eff, lineno), eff, lineno)
            v_sub = _evaluate_inline_exprs(v_sub, vars_, funcs, depth, locals_, lineno,
                                           source_path, var_meta, placer, seen)
            new_val = _eval_expr(v_sub, lineno)
        elems = list(existing)
        elems[idx_int] = new_val
        new_tuple = tuple(elems)
        _write(name, new_tuple, vars_, locals_, var_meta, lineno)
        _maybe_trace(name, vars_, var_meta)
        return

    m = _ASSIGNMENT_RE.match(stmt)
    if m:
        name, op, expr_raw = m.group(1), m.group(2), m.group(3).strip()
        if name.startswith('__'):
            raise ParseError(f"Line {lineno}: names starting with '__' are reserved for system variables")
        if name in _ALL_KEYWORDS:
            raise ParseError(f"Line {lineno}: '{name}' is a reserved keyword and cannot be assigned")
        eff = _effective_vars(vars_, locals_)
        existing = eff.get(name)
        is_tuple_ctx = isinstance(existing, tuple) or _rhs_is_tuple_expr(expr_raw, eff)
        if is_tuple_ctx:
            if op in ('*', '/') and not isinstance(existing, tuple):
                raise ParseError(f"Line {lineno}: '*=' and '/=' are only valid on tuple variables")
            rhs_val = _eval_tuple_expr(expr_raw, eff, lineno, funcs, depth, locals_,
                                        source_path, var_meta, placer, seen)
            if op is None:
                new_tval = rhs_val
            elif op == '+':
                lhs = existing if isinstance(existing, tuple) else ()
                new_tval = _tuple_op(lhs, rhs_val, '+', lineno)
            elif op == '-':
                lhs = existing if isinstance(existing, tuple) else ()
                new_tval = _tuple_op(lhs, rhs_val, '-', lineno)
            elif op == '*':
                lhs = existing if isinstance(existing, tuple) else ()
                new_tval = _tuple_op(lhs, rhs_val, '*', lineno)
            elif op == '/':
                lhs = existing if isinstance(existing, tuple) else ()
                new_tval = _tuple_op(lhs, rhs_val, '/', lineno)
            else:
                new_tval = rhs_val
            _write(name, new_tval, vars_, locals_, var_meta, lineno)
            _maybe_trace(name, vars_, var_meta)
            return
        is_string_ctx = isinstance(existing, str) or _rhs_is_string_expr(expr_raw, eff)
        if is_string_ctx:
            if op in ('-', '*', '/'):
                raise ParseError(f"Line {lineno}: '{op}=' is not defined on string variables")
            value_s = _eval_string_expr(expr_raw, eff, lineno, funcs, depth, locals_,
                                        source_path, var_meta, placer, seen)
            if op is None:
                new_sv: float | str = value_s
            else:
                prev = existing if isinstance(existing, str) else ""
                new_sv = prev + value_s
            _write(name, new_sv, vars_, locals_, var_meta, lineno)
            _maybe_trace(name, vars_, var_meta)
            return
        if op in ('*', '/'):
            raise ParseError(f"Line {lineno}: '{op}=' is only valid on tuple variables")
        expr_sub = _substitute_tuple_indexing(_substitute_vars(expr_raw, eff, lineno), eff, lineno)
        expr_sub = _evaluate_inline_exprs(expr_sub, vars_, funcs, depth, locals_, lineno,
                                          source_path, var_meta, placer, seen)
        def _sub_bare(m: re.Match, _v: dict = eff, _l: int = lineno) -> str:  # type: ignore[type-arg]
            n_ = m.group()
            if n_ in _RESERVED_EXPR_NAMES:
                return n_
            val = _v.get(n_)
            if isinstance(val, float):
                return _fmt_float(val)
            return n_
        expr_sub = _BARE_ID_RE.sub(_sub_bare, expr_sub)
        value_n = _eval_expr(expr_sub, lineno)
        if op is None:
            new_nv: float | str | TupleVal = value_n
        else:
            old_n = eff.get(name, 0.0)
            if not isinstance(old_n, float):
                old_n = 0.0
            if op == '+':
                new_nv = old_n + value_n
            else:
                new_nv = old_n - value_n
        _write(name, new_nv, vars_, locals_, var_meta, lineno)
        _maybe_trace(name, vars_, var_meta)
        return

    # Call-as-statement: user-defined function call (e.g. `draw_box(10, 20)`)
    m_call = _CALL_STMT_RE.match(stmt)
    if m_call:
        fname = m_call.group(1)
        if fname in funcs:
            paren_pos = stmt.index('(', len(fname))
            args, _ = _parse_call_args(stmt, paren_pos, vars_, funcs, depth, locals_, lineno,
                                       source_path, var_meta, placer, seen)
            _invoke_function(funcs[fname], args, lineno, source_path, vars_, var_meta,
                             funcs, depth, placer, seen)
            return

    eff = _effective_vars(vars_, locals_)
    sub_stmt = _substitute_vars(stmt, eff, lineno)
    sub_stmt = _evaluate_inline_exprs(sub_stmt, vars_, funcs, depth, locals_, lineno,
                                      source_path, var_meta, placer, seen)
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
    funcs: dict[str, _FuncDef],
    depth: list[int],
    locals_: dict[str, float | str | TupleVal] | None = None,
    source_path: Path | None = None,
    placer: object = None,
    seen: frozenset[Path] | None = None,
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

    eff = _effective_vars(vars_, locals_)
    if expr_raw is None:
        if type_name == "tuple":
            for name in names:
                _write(name, (), vars_, locals_, var_meta, lineno)
                _maybe_trace(name, vars_, var_meta)
        else:
            default: float | str = "" if type_name == "string" else 0.0
            for name in names:
                _write(name, default, vars_, locals_, var_meta, lineno)
                _maybe_trace(name, vars_, var_meta)
        return

    expr_raw = expr_raw.strip()
    if type_name == "string":
        val_s: float | str | TupleVal = _eval_string_expr(expr_raw, eff, lineno, funcs, depth, locals_,
                                                           source_path, var_meta, placer, seen)
    elif type_name == "tuple":
        val_s = _eval_tuple_expr(expr_raw, eff, lineno, funcs, depth, locals_,
                                 source_path, var_meta, placer, seen)
    else:
        expr_sub = _substitute_tuple_indexing(_substitute_vars(expr_raw, eff, lineno), eff, lineno)
        expr_sub = _evaluate_inline_exprs(expr_sub, vars_, funcs, depth, locals_, lineno,
                                          source_path, var_meta, placer, seen)
        val_s = _eval_expr(expr_sub, lineno)
    _write(names[0], val_s, vars_, locals_, var_meta, lineno)
    _maybe_trace(names[0], vars_, var_meta)


def _execute_unpack(
    match: re.Match,
    lineno: int,
    vars_: dict[str, float | str | TupleVal],
    var_meta: VarMeta,
    funcs: dict[str, _FuncDef],
    depth: list[int],
    locals_: dict[str, float | str | TupleVal] | None = None,
    source_path: Path | None = None,
    placer: object = None,
    seen: frozenset[Path] | None = None,
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
    eff = _effective_vars(vars_, locals_)
    tval = _eval_tuple_expr(expr_raw, eff, lineno, funcs, depth, locals_,
                            source_path, var_meta, placer, seen)
    if len(tval) != len(names):
        raise ParseError(
            f"Line {lineno}: unpack length mismatch — {len(names)} names but tuple has {len(tval)} elements"
        )
    for name, elem in zip(names, tval):
        _write(name, elem, vars_, locals_, var_meta, lineno)
        _maybe_trace(name, vars_, var_meta)


def _trace_output(text: str, t: _Trace) -> None:
    if t.filepath:
        with open(t.filepath, 'a') as f:
            f.write(text + '\n')
    else:
        print(text, file=sys.stderr)


def _maybe_trace(name: str, vars_: dict[str, float | str | TupleVal], var_meta: VarMeta) -> None:
    t = _current_trace
    if t is None or not t.active:
        return
    if t.watch is not None and name not in t.watch:
        return
    fn, ln = var_meta.get(name, ("", 0))
    val = vars_.get(name)
    tc = "T" if isinstance(val, tuple) else "S" if isinstance(val, str) else "N"
    val_str = _vardump_format_value(val)
    t.log.append((name, tc, fn, ln, val_str))
    # Blank line whenever source location changes
    cur_loc = (fn, ln)
    if t.last_loc is not None and t.last_loc != cur_loc:
        _trace_output("", t)
    t.last_loc = cur_loc
    loc = f"{fn}:{ln}" if fn else ("-" if not ln else f":{ln}")
    _trace_output(f"[TRACE] {name:<20} {tc}  {loc:<30}  {val_str}", t)


def _execute_vartrace(
    stmt: str,
    lineno: int,
    source_path: Path | None,
) -> None:
    t = _current_trace
    if t is None:
        return
    rest = stmt.split(None, 1)[1].strip() if len(stmt.split(None, 1)) > 1 else ""

    # Empty args → trace all variables
    if not rest:
        t.watch = None
        t.active = True
        return

    # Tuple argument: "(..." or just "()"
    names: set[str] | None = None
    filepath_part = rest
    if rest.startswith('('):
        end = rest.find(')')
        if end < 0:
            raise ParseError(f"Line {lineno}: vartrace: unmatched '('")
        inner = rest[1:end].strip()
        filepath_part = rest[end + 1:].strip()
        if not inner:
            # () → stop tracing
            t.active = False
            return
        names = set()
        for piece in inner.split(','):
            piece = piece.strip()
            if len(piece) >= 2 and piece[0] in ('"', "'") and piece[-1] == piece[0]:
                names.add(piece[1:-1])
            elif piece:
                raise ParseError(f"Line {lineno}: vartrace: variable names must be quoted strings, got {piece!r}")

    # Optional filepath
    if filepath_part:
        if filepath_part.startswith('"') and filepath_part.endswith('"') and len(filepath_part) >= 2:
            fp = filepath_part[1:-1]
        else:
            fp = filepath_part
        out_path = Path(fp)
        if not out_path.is_absolute():
            base = source_path.parent if source_path else Path.cwd()
            out_path = (base / out_path).resolve()
        t.filepath = str(out_path)

    t.watch = names  # None = all variables
    t.active = True


def _print_trace_summary(t: _Trace, source_path: Path | None) -> None:
    if not t.log:
        return
    # Sort by name, preserving execution order within each name.
    # Within each name suppress consecutive entries with the same value (keep
    # the first occurrence = initialization, then only actual value changes).
    by_name: dict[str, list] = {}
    for entry in t.log:
        by_name.setdefault(entry[0], []).append(entry)
    sorted_rows = []
    for name in sorted(by_name):
        prev_val: str | None = None
        for entry in by_name[name]:
            if entry[4] != prev_val:   # entry[4] is val_str
                sorted_rows.append(entry)
                prev_val = entry[4]

    name_w = max((len(r[0]) for r in sorted_rows), default=4)
    name_w = max(name_w, 4)
    file_w = max((len(r[2]) for r in sorted_rows), default=4)
    file_w = max(file_w, 4)
    line_w = max((len(str(r[3])) for r in sorted_rows), default=4)
    line_w = max(line_w, 4)
    header = f"{'NAME':<{name_w}}  TYPE  {'FILE':<{file_w}}  {'LINE':>{line_w}}  VALUE"
    sep    = f"{'----':<{name_w}}  ----  {'----':<{file_w}}  {'----':>{line_w}}  -----"
    data_lines: list[str] = []
    prev_name: str | None = None
    prev_file: str | None = None
    for r in sorted_rows:
        if prev_name is not None and (r[0] != prev_name or r[2] != prev_file):
            data_lines.append("")
        data_lines.append(f"{r[0]:<{name_w}}  {r[1]:<4}  {r[2]:<{file_w}}  {str(r[3]):>{line_w}}  {r[4]}")
        prev_name = r[0]
        prev_file = r[2]
    lines  = ["=== VARTRACE SUMMARY ===", header, sep] + data_lines
    text = '\n'.join(lines)
    if t.filepath:
        with open(t.filepath, 'a') as f:
            f.write('\n' + text + '\n')
    else:
        print('\n' + text, file=sys.stderr)


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
    funcs: dict[str, _FuncDef],
    depth: list[int],
    placer: ElementPlacer,
    seen: frozenset[Path],
    locals_: dict[str, float | str | TupleVal] | None = None,
) -> None:
    if len(tokens) < 2:
        raise ParseError(f"Line {lineno}: include requires a filename")

    raw = tokens[1].value if tokens[1].kind == "QUOTED" else " ".join(t.value for t in tokens[1:])
    eff = _effective_vars(vars_, locals_)
    if raw.startswith('$'):
        raw = _substitute_vars(raw, eff, lineno)
    elif re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', raw):
        val = eff.get(raw)
        if isinstance(val, str):
            raw = val
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
    _execute_text(inc_path.read_text(), inc_path, vars_, var_meta, funcs, depth, placer, seen | {inc_path}, locals_)
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


def _evaluate_inline_exprs(
    text: str,
    vars_: dict[str, float | str | TupleVal],
    funcs: dict[str, _FuncDef] | None = None,
    depth: list[int] | None = None,
    locals_: dict[str, float | str | TupleVal] | None = None,
    lineno: int = 0,
    source_path: Path | None = None,
    var_meta: VarMeta | None = None,
    placer: object = None,
    seen: frozenset[Path] | None = None,
) -> str:
    """Replace builtin calls and (expr) groups outside quoted strings with their values.

    Builtin calls (`len(s)`, `match(s, p)`, ...) are substituted first at any
    position. Then each remaining (expr) group is evaluated with bare
    identifiers inside resolved as variable references. Quoted strings are
    skipped throughout.
    """
    _funcs = funcs if funcs is not None else {}
    _depth = depth if depth is not None else [0]
    eff = _effective_vars(vars_, locals_)
    text = _substitute_tuple_indexing(text, eff, lineno)
    text = _substitute_builtins_in_expr(text, vars_, _funcs, _depth, locals_, lineno,
                                        source_path, var_meta, placer, seen)
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
            pdepth = 1
            while j < len(text) and pdepth > 0:
                if text[j] == '(':
                    pdepth += 1
                elif text[j] == ')':
                    pdepth -= 1
                j += 1
            if pdepth != 0:
                result.append(ch)
                i += 1
            else:
                inner = text[i + 1:j - 1]
                # tuple literal (x, y) — if inner has a top-level comma, emit as COORD;
                # 4-element tuples are kept parenthesized for rect corner syntax
                if _has_top_level_comma(inner):
                    tval = _eval_tuple_expr(inner, eff, lineno)
                    flat = ','.join(
                        v if isinstance(v, str) else _fmt_float(v)
                        for v in tval
                    )
                    if len(tval) == 4:
                        result.append('(' + flat + ')')
                    elif len(tval) == 2:
                        result.append(flat)
                    else:
                        raise ParseError(
                            f"Line {lineno}: inline tuple must have 2 or 4 elements, got {len(tval)}"
                        )
                    i = j
                else:
                    # Substitute any nested function/builtin calls inside before
                    # resolving bare variable names.
                    inner = _substitute_builtins_in_expr(inner, vars_, _funcs, _depth, locals_, lineno,
                                                        source_path, var_meta, placer, seen)
                    def sub_id(m: re.Match, _v: dict = eff, _l: int = lineno) -> str:  # type: ignore[type-arg]
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


def _evaluate_inline_exprs_bare(
    text: str,
    vars_: dict[str, float | str | TupleVal],
    funcs: dict[str, _FuncDef] | None = None,
    depth: list[int] | None = None,
    locals_: dict[str, float | str | TupleVal] | None = None,
    lineno: int = 0,
    source_path: Path | None = None,
    var_meta: VarMeta | None = None,
    placer: object = None,
    seen: frozenset[Path] | None = None,
) -> str:
    """Like _evaluate_inline_exprs but also substitutes bare identifiers at the top level.

    Used for evaluating condition expressions and for/step bounds that are not
    wrapped in parentheses.
    """
    _funcs = funcs if funcs is not None else {}
    _depth = depth if depth is not None else [0]
    eff = _effective_vars(vars_, locals_)
    text = _substitute_tuple_indexing(text, eff, lineno)
    text = _substitute_builtins_in_expr(text, vars_, _funcs, _depth, locals_, lineno,
                                        source_path, var_meta, placer, seen)
    def sub_id(m: re.Match, _v: dict = eff, _l: int = lineno) -> str:  # type: ignore[type-arg]
        name = m.group()
        if name in _RESERVED_EXPR_NAMES:
            return name
        val = _v.get(name, 0.0)
        if isinstance(val, str):
            raise ParseError(f"Line {_l}: variable '{name}' is a string, not numeric")
        if isinstance(val, tuple):
            raise ParseError(f"Line {_l}: variable '{name}' is a tuple, not numeric")
        return _fmt_float(val)
    # Substitute bare identifiers outside quoted sections
    bare_result: list[str] = []
    i = 0
    n = len(text)
    in_quote: str | None = None
    while i < n:
        ch = text[i]
        if in_quote:
            bare_result.append(ch)
            if ch == in_quote:
                in_quote = None
            i += 1
        elif ch in ('"', "'"):
            in_quote = ch
            bare_result.append(ch)
            i += 1
        else:
            bm = _BARE_ID_RE.match(text, i)
            if bm:
                bare_result.append(sub_id(bm))
                i = bm.end()
            else:
                bare_result.append(ch)
                i += 1
    return ''.join(bare_result)


def _parse_call_args(
    text: str,
    paren_pos: int,
    vars_: dict[str, float | str | TupleVal],
    funcs: dict[str, _FuncDef],
    depth: list[int],
    locals_: dict[str, float | str | TupleVal] | None,
    lineno: int,
    source_path: Path | None = None,
    var_meta: VarMeta | None = None,
    placer: object = None,
    seen: frozenset[Path] | None = None,
) -> tuple[list[object], int]:
    """Parse a comma-separated argument list starting at the `(` at paren_pos.

    Returns (args, position_after_closing_paren). Each arg is one of:
      - quoted string literal ("..." or '...')
      - bare identifier resolved against effective vars (may yield str or float)
      - numeric literal
      - nested builtin or user-function call (resolved recursively)
    Compound numeric expressions (e.g. `x + 1`) are NOT supported as args.
    """
    if paren_pos >= len(text) or text[paren_pos] != '(':
        raise ParseError(f"Line {lineno}: expected '(' in function call")
    i = paren_pos + 1
    n = len(text)
    args: list[object] = []
    eff = _effective_vars(vars_, locals_)
    _seen = seen if seen is not None else frozenset()
    _vm: VarMeta = var_meta if var_meta is not None else {}

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
                # Builtins take priority (guaranteed no collision with user funcs at def time)
                if name in BUILTINS:
                    inner_args, end = _parse_call_args(text, k, vars_, funcs, depth, locals_, lineno,
                                                       source_path, _vm, placer, _seen)
                    args.append(BUILTINS[name](inner_args, lineno))
                    i = end
                elif name in funcs:
                    inner_args, end = _parse_call_args(text, k, vars_, funcs, depth, locals_, lineno,
                                                       source_path, _vm, placer, _seen)
                    args.append(_invoke_function(funcs[name], inner_args, lineno, source_path, vars_, _vm,
                                                 funcs, depth, placer, _seen))
                    i = end
                else:
                    raise ParseError(f"Line {lineno}: unknown function {name!r}")
            else:
                args.append(eff.get(name, 0.0))
                i = j
        elif ch == '(':
            # Parenthesized expression — evaluate as numeric
            j = i + 1
            pd = 1
            while j < n and pd > 0:
                if text[j] == '(':
                    pd += 1
                elif text[j] == ')':
                    pd -= 1
                j += 1
            if pd != 0:
                raise ParseError(f"Line {lineno}: unterminated '(' in argument list")
            inner_expr = text[i + 1:j - 1]
            # Substitute function calls and vars inside, then eval
            inner_expr = _substitute_builtins_in_expr(inner_expr, vars_, funcs, depth, locals_, lineno)
            def _sub_arg_id(m: re.Match, _v: dict = eff, _l: int = lineno) -> str:  # type: ignore[type-arg]
                name = m.group()
                if name in _RESERVED_EXPR_NAMES:
                    return name
                val = _v.get(name, 0.0)
                if isinstance(val, (str, tuple)):
                    raise ParseError(f"Line {_l}: variable {name!r} is not numeric")
                return _fmt_float(float(val))
            inner_expr = _BARE_ID_RE.sub(_sub_arg_id, inner_expr)
            args.append(_eval_expr(inner_expr, lineno))
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
    funcs: dict[str, _FuncDef],
    depth: list[int],
    locals_: dict[str, float | str | TupleVal] | None,
    lineno: int,
    source_path: Path | None = None,
    var_meta: VarMeta | None = None,
    placer: object = None,
    seen: frozenset[Path] | None = None,
) -> str:
    """Replace numeric-returning builtin/user-function calls with their decimal value.

    Walks `text` skipping content inside "..." and '...' string literals.
    `substr`/`replace` (string-returning builtins) raise ParseError — they're only valid
    in string-expression context.  User functions that return strings also raise ParseError
    when used in a numeric expression context.
    """
    _seen = seen if seen is not None else frozenset()
    _vm: VarMeta = var_meta if var_meta is not None else {}
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
            args, after = _parse_call_args(text, paren_pos, vars_, funcs, depth, locals_, lineno,
                                           source_path, _vm, placer, _seen)
            if name in BUILTIN_RETURNS_STRING:
                raise ParseError(
                    f"Line {lineno}: {name}() returns a string and is not valid in a numeric expression"
                )
            result = BUILTINS[name](args, lineno)
            out.append(_fmt_float(float(result)))
            i = after
            continue
        # Check for user-defined function call in numeric-expression context
        m_uf = _CALL_EXPR_RE.match(text, i)
        if m_uf and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == '_')):
            fname = m_uf.group(1)
            if fname in funcs:
                paren_pos = m_uf.end() - 1
                args_uf, after_uf = _parse_call_args(text, paren_pos, vars_, funcs, depth, locals_, lineno,
                                                     source_path, _vm, placer, _seen)
                ret = _invoke_function(funcs[fname], args_uf, lineno, source_path, vars_, _vm,
                                       funcs, depth, placer, _seen)
                if isinstance(ret, str):
                    raise ParseError(
                        f"Line {lineno}: function {fname!r} returns a string and is not valid in a numeric expression"
                    )
                if isinstance(ret, tuple):
                    raise ParseError(
                        f"Line {lineno}: function {fname!r} returns a tuple and is not valid in a numeric expression"
                    )
                out.append(_fmt_float(float(ret)))
                i = after_uf
                continue
        out.append(ch)
        i += 1
    return ''.join(out)


def _eval_string_expr(
    text: str,
    vars_: dict[str, float | str | TupleVal],
    lineno: int,
    funcs: dict[str, _FuncDef] | None = None,
    depth: list[int] | None = None,
    locals_: dict[str, float | str | TupleVal] | None = None,
    source_path: Path | None = None,
    var_meta: VarMeta | None = None,
    placer: object = None,
    seen: frozenset[Path] | None = None,
) -> str:
    """Evaluate a string expression: terms joined by `+`.

    Each term is: a quoted literal, a bare variable reference (must be string),
    a ${name}/$name reference, or a string-returning builtin/user-function call.
    Numeric terms (literals, numeric vars, len/match results) raise ParseError —
    there is no implicit numeric-to-string coercion.
    """
    _funcs = funcs if funcs is not None else {}
    _depth = depth if depth is not None else [0]
    eff = _effective_vars(vars_, locals_)
    # Pre-substitute tuple indexing so name[i] yields the slot's string value
    text = _substitute_tuple_indexing(text, eff, lineno)
    parts: list[str] = []
    i = 0
    n = len(text)
    expect_term = True

    def lookup_str(name: str) -> str:
        val = eff.get(name)
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
                    if name in BUILTINS:
                        args, end = _parse_call_args(text, k, vars_, _funcs, _depth, locals_, lineno)
                        if name in BUILTIN_RETURNS_NUMERIC:
                            raise ParseError(
                                f"Line {lineno}: {name}() returns a numeric value, cannot be used in a string expression"
                            )
                        parts.append(BUILTINS[name](args, lineno))
                        i = end
                    elif name in _funcs:
                        _vm: VarMeta = var_meta if var_meta is not None else {}
                        _seen = seen if seen is not None else frozenset()
                        args, end = _parse_call_args(text, k, vars_, _funcs, _depth, locals_, lineno,
                                                     source_path, _vm, placer, _seen)
                        ret = _invoke_function(_funcs[name], args, lineno, source_path, vars_, _vm,
                                               _funcs, _depth, placer, _seen)
                        if not isinstance(ret, str):
                            raise ParseError(
                                f"Line {lineno}: function {name!r} does not return a string; cannot be used in a string expression"
                            )
                        parts.append(ret)
                        i = end
                    else:
                        raise ParseError(f"Line {lineno}: unknown function {name!r}")
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


def _rhs_is_string_expr(text: str, vars_: dict[str, float | str | TupleVal] | None = None) -> bool:
    """Quick check: does the RHS look like a string expression?

    Used to dispatch plain `name = expr` assignments when the LHS is not
    already-typed as a string variable.
    """
    stripped = text.strip()
    if not stripped:
        return False
    if stripped[0] in ('"', "'"):
        return True
    if vars_ is None:
        return False
    if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', stripped):
        return isinstance(vars_.get(stripped), str)
    m_ref = re.fullmatch(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)', stripped)
    if m_ref:
        name = m_ref.group(1) if m_ref.group(1) is not None else m_ref.group(2)
        return isinstance(vars_.get(name), str)
    return False


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
    funcs: dict[str, _FuncDef] | None = None,
    depth: list[int] | None = None,
    locals_: dict[str, float | str | TupleVal] | None = None,
    source_path: Path | None = None,
    var_meta: VarMeta | None = None,
    placer: object = None,
    seen: frozenset[Path] | None = None,
) -> TupleVal:
    """Evaluate a tuple expression and return a TupleVal."""
    _funcs = funcs if funcs is not None else {}
    _depth = depth if depth is not None else [0]
    text = text.strip()

    # User-defined function call returning a tuple
    m_call = _CALL_STMT_RE.match(text)
    if m_call:
        fname = m_call.group(1)
        if fname in _funcs:
            _vm2: VarMeta = var_meta if var_meta is not None else {}
            _seen2 = seen if seen is not None else frozenset()
            paren_pos = text.index('(', len(fname))
            args, _ = _parse_call_args(text, paren_pos, vars_, _funcs, _depth, locals_, lineno,
                                       source_path, _vm2, placer, _seen2)
            ret = _invoke_function(_funcs[fname], args, lineno, source_path, vars_, _vm2,
                                   _funcs, _depth, placer, _seen2)
            if not isinstance(ret, tuple):
                return (ret,)  # type: ignore[return-value]
            return ret

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
    """Split on top-level commas and evaluate each element.

    If an element is a bare identifier or $ref resolving to a tuple variable,
    its elements are spread (flattened) into the result. Otherwise the element
    is evaluated as a scalar.
    """
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

    elements: list[float | str] = []
    for p in parts:
        t = p.strip()
        # bare tuple var → spread its elements
        if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', t):
            val = vars_.get(t)
            if isinstance(val, tuple):
                elements.extend(val)
                continue
        # $name / ${name} → spread if tuple
        m_ref = re.fullmatch(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)', t)
        if m_ref:
            name = m_ref.group(1) if m_ref.group(1) is not None else m_ref.group(2)
            val = vars_.get(name)
            if isinstance(val, tuple):
                elements.extend(val)
                continue
        elements.append(_eval_scalar_element(t, vars_, lineno))
    return tuple(elements)


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
    expr_sub = _evaluate_inline_exprs(expr_sub, vars_, lineno=lineno)
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
                idx_sub = _evaluate_inline_exprs(idx_sub, vars_, lineno=lineno)
                idx_float = _eval_expr(idx_sub, lineno)
                if idx_float != int(idx_float) or int(idx_float) < 0:
                    raise ParseError(f"Line {lineno}: tuple index must be a non-negative integer")
                idx_int = int(idx_float)
                if idx_int >= len(val):
                    raise ParseError(
                        f"Line {lineno}: tuple index {idx_int} out of range (len={len(val)})"
                    )
                slot = val[idx_int]
                if isinstance(slot, str):
                    # Wrap in quotes so _eval_string_expr treats it as a literal,
                    # not a bare identifier.  Escape backslash and \n for round-trip
                    # safety (the DSL string-literal parser converts \\n → \n).
                    escaped = slot.replace('\\', '\\\\').replace('\n', '\\n')
                    result.append('"' + escaped + '"')
                else:
                    result.append(_fmt_float(slot))
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
    for sysname, val in (
        ("__cursorx", cx), ("__cursory", cy),
        ("__cx", cx),      ("__cy", cy),
        ("__cursor", (cx, cy)),
        ("__dir", placer._cursor.direction),
        ("__mltodir", placer._mltodir),
    ):
        vars_[sysname] = val
        var_meta[sysname] = (fn, ln)
        _maybe_trace(sysname, vars_, var_meta)
