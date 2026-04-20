from .ast import (
    ASTNode, DirectionDirective,
    LineElem, RectElem, WallElem, DoorElem, WindowElem,
    ArcElem, ArrowElem, LabelElem,
)
from .lexer import Token, tokenize, parse_measurement, parse_coord, parse_absolute


class ParseError(Exception):
    pass


def parse_file(text: str) -> list[ASTNode]:
    nodes: list[ASTNode] = []
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#")[0].strip()
        if not line:
            continue
        tokens = tokenize(line, lineno)
        if not tokens:
            continue
        node = _parse_line(tokens, lineno)
        if node is not None:
            nodes.append(node)
    return nodes


def _parse_line(tokens: list[Token], lineno: int) -> ASTNode | None:
    keyword = tokens[0].value.lower()
    rest = tokens[1:]

    if keyword == "direction":
        return _parse_direction(rest, lineno)
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
    if keyword == "label":
        return _parse_label(rest, lineno)

    raise ParseError(f"Line {lineno}: unknown element type {keyword!r}")


# ── directives ────────────────────────────────────────────────────────────────

def _parse_direction(tokens: list[Token], lineno: int) -> DirectionDirective:
    if not tokens:
        raise ParseError(f"Line {lineno}: direction requires a value")
    deg = float(tokens[0].value)
    return DirectionDirective(degrees=deg, source_line=lineno)


# ── helpers ───────────────────────────────────────────────────────────────────

def _extract_common(tokens: list[Token], lineno: int) -> dict:
    """Pull lw, coords (begin/end), absolute, quoted label from a token list."""
    result: dict = {"lw": None, "begin": None, "end": None, "absolute": None, "label": None}
    coords_found: list[tuple[float, float]] = []

    for tok in tokens:
        if tok.kind == "PX":
            result["lw"] = float(tok.value)
        elif tok.kind == "ABSOLUTE":
            result["absolute"] = parse_absolute(tok)
        elif tok.kind == "COORD":
            coords_found.append(parse_coord(tok))
        elif tok.kind == "QUOTED":
            result["label"] = tok.value

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
    return LineElem(length=length, lw=c["lw"], begin=c["begin"], end=c["end"],
                    absolute=c["absolute"], source_line=lineno)


def _parse_rect(tokens: list[Token], lineno: int) -> RectElem:
    length, width = _leading_measurements(tokens, 2, lineno)
    c = _extract_common(tokens, lineno)
    return RectElem(length=length, width=width, lw=c["lw"], label=c["label"],
                    begin=c["begin"], end=c["end"], absolute=c["absolute"],
                    source_line=lineno)


def _parse_wall(tokens: list[Token], lineno: int) -> WallElem:
    dims = _leading_measurements(tokens, 1, lineno)
    length = dims[0]
    # optional second measurement = thickness
    all_dims = _leading_measurements(tokens, 2, lineno) if sum(
        1 for t in tokens if t.kind in ("MEASUREMENT", "NUMBER")
    ) >= 2 else [length, 0.5]
    thickness = all_dims[1] if len(all_dims) > 1 else 0.5
    c = _extract_common(tokens, lineno)
    return WallElem(length=length, thickness=thickness, lw=c["lw"],
                    begin=c["begin"], end=c["end"], absolute=c["absolute"],
                    source_line=lineno)


def _parse_door(tokens: list[Token], lineno: int) -> DoorElem:
    (width,) = _leading_measurements(tokens, 1, lineno)
    swing = "right"
    for tok in tokens:
        if tok.kind == "WORD" and tok.value.lower() in ("left", "right", "in", "out"):
            swing = tok.value.lower()
    c = _extract_common(tokens, lineno)
    return DoorElem(width=width, swing=swing, lw=c["lw"], absolute=c["absolute"],
                    source_line=lineno)


def _parse_window(tokens: list[Token], lineno: int) -> WindowElem:
    dims_count = sum(1 for t in tokens if t.kind in ("MEASUREMENT", "NUMBER"))
    dims = _leading_measurements(tokens, min(dims_count, 2), lineno)
    width = dims[0]
    depth = dims[1] if len(dims) > 1 else 0.5
    c = _extract_common(tokens, lineno)
    return WindowElem(width=width, depth=depth, lw=c["lw"], absolute=c["absolute"],
                      source_line=lineno)


def _parse_arc(tokens: list[Token], lineno: int) -> ArcElem:
    radius, sweep = _leading_measurements(tokens, 2, lineno)
    c = _extract_common(tokens, lineno)
    return ArcElem(radius=radius, sweep=sweep, lw=c["lw"], absolute=c["absolute"],
                   source_line=lineno)


def _parse_arrow(tokens: list[Token], lineno: int) -> ArrowElem:
    (length,) = _leading_measurements(tokens, 1, lineno)
    c = _extract_common(tokens, lineno)
    return ArrowElem(length=length, lw=c["lw"], absolute=c["absolute"],
                     source_line=lineno)


def _parse_label(tokens: list[Token], lineno: int) -> LabelElem:
    text = ""
    align = "left"
    absolute = None
    for tok in tokens:
        if tok.kind == "QUOTED":
            text = tok.value
        elif tok.kind == "WORD" and tok.value.lower() in ("left", "center", "right"):
            align = tok.value.lower()
        elif tok.kind == "ABSOLUTE":
            absolute = parse_absolute(tok)
    if not text:
        # bare word after label keyword
        if tokens and tokens[0].kind == "WORD":
            text = tokens[0].value
    return LabelElem(text=text, align=align, absolute=absolute, source_line=lineno)
