from pathlib import Path
from .ast import (
    ASTNode, DirectionDirective, DisplayDirective, ColorDirective,
    ShowCornerXYDirective,
    LineElem, RectElem, WallElem, DoorElem, WindowElem,
    ArcElem, ArrowElem, CircleElem, PointElem, LabelElem,
    MoveToElem, LineToElem,
    TextStyleDirective, TextLineElem, TextBreakElem, TextBoxElem, TextAppendElem,
)
from .lexer import Token, tokenize, parse_measurement, parse_coord, parse_absolute


class ParseError(Exception):
    pass


def _strip_comment(raw: str) -> str:
    """Strip trailing # comment, ignoring # inside double-quoted strings."""
    in_quote = False
    for i, ch in enumerate(raw):
        if ch == '"':
            in_quote = not in_quote
        elif ch == '#' and not in_quote:
            return raw[:i].strip()
    return raw.strip()


def _split_statements(line: str) -> list[str]:
    """Split on semicolons, ignoring those inside double-quoted strings."""
    parts: list[str] = []
    current: list[str] = []
    in_quote = False
    for ch in line:
        if ch == '"':
            in_quote = not in_quote
            current.append(ch)
        elif ch == ';' and not in_quote:
            parts.append(''.join(current))
            current = []
        else:
            current.append(ch)
    parts.append(''.join(current))
    return parts


def parse_file(
    text: str,
    source_path: Path | None = None,
    _seen: frozenset[Path] | None = None,
) -> list[ASTNode]:
    """Parse DSL text into an AST node list.

    source_path: path of the file being parsed, used to resolve relative includes.
    _seen: set of absolute paths already open in the current include chain
           (used to detect circular includes).
    """
    if _seen is None:
        _seen = frozenset()
    if source_path is not None:
        source_path = source_path.resolve()
        _seen = _seen | {source_path}

    nodes: list[ASTNode] = []
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = _strip_comment(raw_line)
        if not line:
            continue
        for stmt in _split_statements(line):
            stmt = stmt.strip()
            if not stmt:
                continue
            tokens = tokenize(stmt, lineno)
            if not tokens:
                continue
            if _ALIASES.get(tokens[0].value.lower(), tokens[0].value.lower()) == "include":
                nodes.extend(_resolve_include(tokens, lineno, source_path, _seen))
            else:
                node = _parse_line(tokens, lineno)
                if node is not None:
                    nodes.append(node)
    return nodes


def _resolve_include(
    tokens: list[Token],
    lineno: int,
    source_path: Path | None,
    _seen: frozenset[Path],
) -> list[ASTNode]:
    if len(tokens) < 2:
        raise ParseError(f"Line {lineno}: include requires a filename")

    # Filename may be quoted or bare
    raw = tokens[1].value if tokens[1].kind == "QUOTED" else " ".join(t.value for t in tokens[1:])
    inc_path = Path(raw)

    # Resolve relative to the including file's directory, or cwd if from stdin
    if not inc_path.is_absolute():
        base = source_path.parent if source_path else Path.cwd()
        inc_path = (base / inc_path).resolve()
    else:
        inc_path = inc_path.resolve()

    if inc_path in _seen:
        raise ParseError(f"Line {lineno}: circular include detected: {inc_path}")

    if not inc_path.exists():
        raise ParseError(f"Line {lineno}: include file not found: {inc_path}")

    return parse_file(inc_path.read_text(), source_path=inc_path, _seen=_seen)


_ALIASES: dict[str, str] = {
    "l":      "line",
    "r":      "rect",
    "w":      "wall",
    "d":      "door",
    "wi":     "window",
    "a":      "arc",
    "aw":     "arrow",
    "ci":     "circle",
    "p":      "point",
    "lb":     "label",
    "dir":    "direction",
    "eid":    "elementid",
    "dim":    "dimensions",
    "col":    "color",
    "inc":    "include",
    "sxy":    "showcornerxy",
    "mto":    "moveto",
    "lto":    "lineto",
    "tstyle": "textstyle",
    "txl":    "textline",
    "txbr":   "textbreak",
    "tbox":   "textbox",
    "tapp":   "textappend",
}


def _parse_line(tokens: list[Token], lineno: int) -> ASTNode | None:
    keyword = _ALIASES.get(tokens[0].value.lower(), tokens[0].value.lower())
    rest = tokens[1:]

    if keyword == "direction":
        return _parse_direction(rest, lineno)
    if keyword == "color":
        return _parse_color(rest, lineno)
    if keyword == "showcornerxy":
        return _parse_showcornerxy(rest, lineno)
    if keyword == "elementid":
        return _parse_display(rest, lineno, "elementid")
    if keyword == "dimensions":
        return _parse_display(rest, lineno, "dimensions")
    if keyword == "line":
        return _parse_line_elem(rest, lineno)
    if keyword == "rect":
        return _parse_rect(rest, lineno)
    if keyword == "wall":
        return _parse_wall(rest, lineno)
    if keyword == "door":
        return _parse_door(rest, lineno)
    if keyword == "window":
        return _parse_window(rest, lineno)
    if keyword == "arc":
        return _parse_arc(rest, lineno)
    if keyword == "arrow":
        return _parse_arrow(rest, lineno)
    if keyword == "circle":
        return _parse_circle(rest, lineno)
    if keyword == "point":
        return _parse_point(rest, lineno)
    if keyword == "label":
        return _parse_label(rest, lineno)
    if keyword == "moveto":
        return _parse_moveto(rest, lineno)
    if keyword == "lineto":
        return _parse_lineto(rest, lineno)
    if keyword == "textstyle":
        return _parse_textstyle(rest, lineno)
    if keyword == "textline":
        return _parse_textline(rest, lineno)
    if keyword == "textbreak":
        return _parse_textbreak(rest, lineno)
    if keyword == "textbox":
        return _parse_textbox(rest, lineno)
    if keyword == "textappend":
        return _parse_textappend(rest, lineno)

    raise ParseError(f"Line {lineno}: unknown element type {keyword!r}")


# ── directives ────────────────────────────────────────────────────────────────

def _parse_showcornerxy(tokens: list[Token], lineno: int) -> ShowCornerXYDirective:
    if not tokens:
        raise ParseError(f"Line {lineno}: showcornerxy requires 'on' or 'off'")
    val = tokens[0].value.lower()
    if val not in ("on", "off"):
        raise ParseError(f"Line {lineno}: showcornerxy requires 'on' or 'off', got {val!r}")
    return ShowCornerXYDirective(enabled=(val == "on"), source_line=lineno)


def _parse_display(tokens: list[Token], lineno: int, target: str) -> DisplayDirective:
    if not tokens:
        raise ParseError(f"Line {lineno}: {target} requires 'on' or 'off'")
    val = tokens[0].value.lower()
    if val not in ("on", "off"):
        raise ParseError(f"Line {lineno}: {target} requires 'on' or 'off', got {val!r}")
    return DisplayDirective(target=target, enabled=(val == "on"), source_line=lineno)


def _parse_color(tokens: list[Token], lineno: int) -> ColorDirective:
    if not tokens:
        raise ParseError(f"Line {lineno}: color requires a value")
    tok = tokens[0]
    if tok.kind == "QUOTED":
        color = tok.value
    elif tok.kind == "WORD":
        color = tok.value.lower()
    else:
        raise ParseError(f"Line {lineno}: color requires a named color or quoted CSS value")
    return ColorDirective(color=color, source_line=lineno)


def _parse_direction(tokens: list[Token], lineno: int) -> DirectionDirective:
    if not tokens:
        raise ParseError(f"Line {lineno}: direction requires a value")
    deg = float(tokens[0].value)
    return DirectionDirective(degrees=deg, source_line=lineno)


# ── helpers ───────────────────────────────────────────────────────────────────

_DASH_STYLES = {"dashed", "shortdash", "dotted", "center", "hidden"}
_ALIGN_WORDS = {"left", "center", "right"}


def _extract_common(tokens: list[Token], lineno: int) -> dict:
    """Pull lw, dash, coords (begin/end), absolute, label, name, font_family from tokens."""
    result: dict = {
        "lw": None, "dash": None, "color": None, "begin": None, "end": None,
        "absolute": None, "label": None, "name": None, "font_family": None,
    }
    coords_found: list[tuple[float, float]] = []

    for tok in tokens:
        if tok.kind == "PX":
            result["lw"] = float(tok.value)
        elif tok.kind == "COLOR_ELEM":
            result["color"] = tok.value
        elif tok.kind == "ABSOLUTE":
            result["absolute"] = parse_absolute(tok)
        elif tok.kind == "COORD":
            coords_found.append(parse_coord(tok))
        elif tok.kind == "QUOTED":
            result["label"] = tok.value
        elif tok.kind == "WORD":
            lv = tok.value.lower()
            if lv in _DASH_STYLES:
                result["dash"] = lv
            elif tok.value.startswith("@") and len(tok.value) > 1:
                result["name"] = tok.value[1:]
            elif lv.startswith("font=") and len(lv) > 5:
                result["font_family"] = tok.value[5:]  # preserve case for CSS

    if len(coords_found) >= 1:
        result["begin"] = coords_found[0]
    if len(coords_found) >= 2:
        result["end"] = coords_found[1]

    return result


def _leading_measurements(tokens: list[Token], count: int, lineno: int) -> list[float]:
    """Extract the first `count` measurement/number tokens from the list."""
    vals: list[float] = []
    for tok in tokens:
        if tok.kind in ("MEASUREMENT", "NUMBER"):
            vals.append(parse_measurement(tok))
            if len(vals) == count:
                break
    if len(vals) < count:
        raise ParseError(f"Line {lineno}: expected {count} dimension(s), got {len(vals)}")
    return vals


# ── element parsers ───────────────────────────────────────────────────────────

def _parse_line_elem(tokens: list[Token], lineno: int) -> LineElem:
    (length,) = _leading_measurements(tokens, 1, lineno)
    c = _extract_common(tokens, lineno)
    return LineElem(length=length, lw=c["lw"], dash=c["dash"], color=c["color"],
                    begin=c["begin"], end=c["end"], absolute=c["absolute"],
                    name=c["name"], source_line=lineno)


def _parse_rect(tokens: list[Token], lineno: int) -> RectElem:
    length, width = _leading_measurements(tokens, 2, lineno)
    c = _extract_common(tokens, lineno)
    return RectElem(length=length, width=width, lw=c["lw"], dash=c["dash"], color=c["color"],
                    label=c["label"], begin=c["begin"], end=c["end"], absolute=c["absolute"],
                    name=c["name"], source_line=lineno)


def _parse_wall(tokens: list[Token], lineno: int) -> WallElem:
    dims = _leading_measurements(tokens, 1, lineno)
    length = dims[0]
    # optional second measurement = thickness
    all_dims = _leading_measurements(tokens, 2, lineno) if sum(
        1 for t in tokens if t.kind in ("MEASUREMENT", "NUMBER")
    ) >= 2 else [length, 0.5]
    thickness = all_dims[1] if len(all_dims) > 1 else 0.5
    c = _extract_common(tokens, lineno)
    return WallElem(length=length, thickness=thickness, lw=c["lw"], dash=c["dash"],
                    color=c["color"], begin=c["begin"], end=c["end"],
                    absolute=c["absolute"], name=c["name"], source_line=lineno)


def _parse_door(tokens: list[Token], lineno: int) -> DoorElem:
    (width,) = _leading_measurements(tokens, 1, lineno)
    swing = "right"
    for tok in tokens:
        if tok.kind == "WORD" and tok.value.lower() in ("left", "right", "in", "out"):
            swing = tok.value.lower()
    c = _extract_common(tokens, lineno)
    return DoorElem(width=width, swing=swing, lw=c["lw"], dash=c["dash"],
                    color=c["color"], absolute=c["absolute"], name=c["name"],
                    source_line=lineno)


def _parse_window(tokens: list[Token], lineno: int) -> WindowElem:
    dims_count = sum(1 for t in tokens if t.kind in ("MEASUREMENT", "NUMBER"))
    dims = _leading_measurements(tokens, min(dims_count, 2), lineno)
    width = dims[0]
    depth = dims[1] if len(dims) > 1 else 0.5
    c = _extract_common(tokens, lineno)
    return WindowElem(width=width, depth=depth, lw=c["lw"], dash=c["dash"],
                      color=c["color"], absolute=c["absolute"], name=c["name"],
                      source_line=lineno)


def _parse_arc(tokens: list[Token], lineno: int) -> ArcElem:
    radius, sweep = _leading_measurements(tokens, 2, lineno)
    c = _extract_common(tokens, lineno)
    return ArcElem(radius=radius, sweep=sweep, lw=c["lw"], dash=c["dash"],
                   color=c["color"], absolute=c["absolute"], name=c["name"],
                   source_line=lineno)


def _parse_arrow(tokens: list[Token], lineno: int) -> ArrowElem:
    (length,) = _leading_measurements(tokens, 1, lineno)
    c = _extract_common(tokens, lineno)
    return ArrowElem(length=length, lw=c["lw"], dash=c["dash"],
                     color=c["color"], absolute=c["absolute"], name=c["name"],
                     source_line=lineno)


def _parse_circle(tokens: list[Token], lineno: int) -> CircleElem:
    (radius,) = _leading_measurements(tokens, 1, lineno)
    c = _extract_common(tokens, lineno)
    return CircleElem(radius=radius, lw=c["lw"], dash=c["dash"],
                      color=c["color"], absolute=c["absolute"], name=c["name"],
                      source_line=lineno)


def _parse_point(tokens: list[Token], lineno: int) -> PointElem:
    c = _extract_common(tokens, lineno)
    return PointElem(lw=c["lw"], color=c["color"], absolute=c["absolute"],
                     name=c["name"], source_line=lineno)


def _parse_label(tokens: list[Token], lineno: int) -> LabelElem:
    text = ""
    align = "left"
    font_size = None
    font_family = None
    color = None
    absolute = None
    name = None
    for tok in tokens:
        if tok.kind == "QUOTED":
            text = tok.value
        elif tok.kind == "COLOR_ELEM":
            color = tok.value
        elif tok.kind == "WORD":
            lv = tok.value.lower()
            if lv in _ALIGN_WORDS:
                align = lv
            elif tok.value.startswith("@") and len(tok.value) > 1:
                name = tok.value[1:]
            elif lv.startswith("font=") and len(lv) > 5:
                font_family = tok.value[5:]
        elif tok.kind == "NUMBER":
            font_size = float(tok.value)
        elif tok.kind == "ABSOLUTE":
            absolute = parse_absolute(tok)
    if not text:
        # bare word after label keyword (but not a name tag)
        for tok in tokens:
            if tok.kind == "WORD" and not tok.value.startswith("@"):
                lv = tok.value.lower()
                if lv not in _ALIGN_WORDS and not lv.startswith("font="):
                    text = tok.value
                    break
    return LabelElem(text=text, align=align, font_size=font_size, font_family=font_family,
                     color=color, absolute=absolute, name=name, source_line=lineno)


def _parse_moveto(tokens: list[Token], lineno: int) -> MoveToElem:
    if len(tokens) < 2:
        raise ParseError(f"Line {lineno}: moveto requires dest_x and dest_y")
    dest_x = parse_measurement(tokens[0])
    dest_y = parse_measurement(tokens[1])
    absolute = None
    for tok in tokens[2:]:
        if tok.kind == "ABSOLUTE":
            absolute = parse_absolute(tok)
    return MoveToElem(dest_x=dest_x, dest_y=dest_y, absolute=absolute, source_line=lineno)


def _parse_lineto(tokens: list[Token], lineno: int) -> LineToElem:
    if len(tokens) < 2:
        raise ParseError(f"Line {lineno}: lineto requires dest_x and dest_y")
    dest_x = parse_measurement(tokens[0])
    dest_y = parse_measurement(tokens[1])
    c = _extract_common(tokens[2:], lineno)
    return LineToElem(
        dest_x=dest_x, dest_y=dest_y,
        lw=c["lw"], dash=c["dash"], color=c["color"],
        absolute=c["absolute"], name=c["name"], source_line=lineno,
    )


# ── text feature parsers ──────────────────────────────────────────────────────

def _parse_textstyle(tokens: list[Token], lineno: int) -> TextStyleDirective:
    """textstyle [<size>] [font=<family>] [normal]"""
    size = None
    font_family = None
    for tok in tokens:
        if tok.kind == "NUMBER":
            size = float(tok.value)
        elif tok.kind == "WORD":
            lv = tok.value.lower()
            if lv == "normal":
                size = 10.0
                font_family = "sans-serif"
            elif lv.startswith("font=") and len(lv) > 5:
                font_family = tok.value[5:]
    return TextStyleDirective(size=size, font_family=font_family, source_line=lineno)


def _parse_textline(tokens: list[Token], lineno: int) -> TextLineElem:
    """textline "text" <element_name> [left|center|right] [<size>] [font=<family>] [C=<color>]"""
    text = ""
    element_name = ""
    align = "center"
    font_size = None
    font_family = None
    color = None
    text_found = False
    name_found = False
    for tok in tokens:
        if tok.kind == "QUOTED" and not text_found:
            text = tok.value
            text_found = True
        elif tok.kind == "COLOR_ELEM":
            color = tok.value
        elif tok.kind == "NUMBER" and font_size is None:
            font_size = float(tok.value)
        elif tok.kind == "WORD":
            lv = tok.value.lower()
            if lv in _ALIGN_WORDS:
                align = lv
            elif lv.startswith("font=") and len(lv) > 5:
                font_family = tok.value[5:]
            elif not name_found and not tok.value.startswith("@"):
                element_name = lv
                name_found = True
    if not element_name:
        raise ParseError(f"Line {lineno}: textline requires an element name")
    return TextLineElem(text=text, element_name=element_name, align=align,
                        font_size=font_size, font_family=font_family, color=color,
                        source_line=lineno)


def _parse_textbreak(tokens: list[Token], lineno: int) -> TextBreakElem:
    """textbreak "text" <element_name> [left|center|right] [<size>] [<lw>] [font=<family>] [C=<color>]"""
    text = ""
    element_name = ""
    align = "center"
    font_size = None
    font_family = None
    lw = None
    color = None
    text_found = False
    name_found = False
    for tok in tokens:
        if tok.kind == "QUOTED" and not text_found:
            text = tok.value
            text_found = True
        elif tok.kind == "COLOR_ELEM":
            color = tok.value
        elif tok.kind == "PX":
            lw = float(tok.value)
        elif tok.kind == "NUMBER" and font_size is None:
            font_size = float(tok.value)
        elif tok.kind == "WORD":
            lv = tok.value.lower()
            if lv in _ALIGN_WORDS:
                align = lv
            elif lv.startswith("font=") and len(lv) > 5:
                font_family = tok.value[5:]
            elif not name_found and not tok.value.startswith("@"):
                element_name = lv
                name_found = True
    if not element_name:
        raise ParseError(f"Line {lineno}: textbreak requires an element name")
    return TextBreakElem(text=text, element_name=element_name, align=align,
                         font_size=font_size, font_family=font_family, lw=lw, color=color,
                         source_line=lineno)


def _parse_textbox(tokens: list[Token], lineno: int) -> TextBoxElem:
    """textbox <length> <width> ["text"] [left|center|right] [wrap] [<size>] [font=<family>]
               [C=<color>] [<lw>px] [<dash>] [A=<h>,<v>] [@name]"""
    length, width = _leading_measurements(tokens, 2, lineno)
    c = _extract_common(tokens, lineno)

    wrap = False
    align = "left"
    font_size = None
    font_family = c["font_family"]

    dim_count = 0
    for tok in tokens:
        if tok.kind in ("MEASUREMENT", "NUMBER"):
            dim_count += 1
            if dim_count > 2 and tok.kind == "NUMBER" and font_size is None:
                font_size = float(tok.value)
        elif tok.kind == "WORD":
            lv = tok.value.lower()
            if lv == "wrap":
                wrap = True
            elif lv in _ALIGN_WORDS:
                align = lv

    return TextBoxElem(
        length=length, width=width,
        text=c["label"] or "",
        align=align, wrap=wrap,
        font_size=font_size,
        font_family=font_family,
        lw=c["lw"], dash=c["dash"], color=c["color"],
        absolute=c["absolute"],
        name=c["name"],
        source_line=lineno,
    )


def _parse_textappend(tokens: list[Token], lineno: int) -> TextAppendElem:
    """textappend "text" <element_name> [left|center|right] [<size>] [font=<family>] [C=<color>]"""
    text = ""
    element_name = ""
    align = "left"
    font_size = None
    font_family = None
    color = None
    text_found = False
    name_found = False
    for tok in tokens:
        if tok.kind == "QUOTED" and not text_found:
            text = tok.value
            text_found = True
        elif tok.kind == "COLOR_ELEM":
            color = tok.value
        elif tok.kind == "NUMBER" and font_size is None:
            font_size = float(tok.value)
        elif tok.kind == "WORD":
            lv = tok.value.lower()
            if lv in _ALIGN_WORDS:
                align = lv
            elif lv.startswith("font=") and len(lv) > 5:
                font_family = tok.value[5:]
            elif not name_found and not tok.value.startswith("@"):
                element_name = lv
                name_found = True
    if not element_name:
        raise ParseError(f"Line {lineno}: textappend requires an element name")
    return TextAppendElem(text=text, element_name=element_name, align=align,
                          font_size=font_size, font_family=font_family, color=color,
                          source_line=lineno)
