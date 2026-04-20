"""SVG renderer.

All coordinates emitted here are in SVG user units (pixels at 96dpi).
The scale transform is applied as a pre-computation rather than an SVG
<g transform>, so stroke-width and font-size are always in screen pixels.
"""
import math
from ..model import PlacedElement
from ..layout.cursor import direction_vector
from .dimensions import element_number_svg, dimension_label_svg
from .symbols import defs_svg, door_svg, window_svg

PAGE_W = 1056  # 11in @ 96dpi
PAGE_H = 816   # 8.5in @ 96dpi

DEFAULT_STROKE = 1.0   # SVG pixels
LABEL_FONT = 10        # SVG pixels
DIM_FONT = 8           # SVG pixels
NUM_FONT = 7           # SVG pixels


def render_svg(elements: list[PlacedElement], scale: float, tx: float, ty: float) -> str:
    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{PAGE_W}" height="{PAGE_H}" '
        f'viewBox="0 0 {PAGE_W} {PAGE_H}">'
    )
    lines.append(defs_svg())
    lines.append('  <g id="drawing">')

    for elem in elements:
        geom = _render_element(elem, scale, tx, ty)
        if geom:
            lines.append(f"    {geom}")

    for elem in elements:
        if elem.number is not None:
            lines.append(f"    {element_number_svg(elem, scale, tx, ty)}")
            lines.append(f"    {dimension_label_svg(elem, scale, tx, ty)}")
        if elem.kind == "rect" and elem.label:
            lines.append(f"    {_label_for_rect(elem, scale, tx, ty)}")
        if elem.kind == "label":
            lines.append(f"    {_label_svg(elem, scale, tx, ty)}")

    lines.append("  </g>")
    lines.append("</svg>")
    return "\n".join(lines)


def _px(val: float, scale: float, offset: float) -> float:
    return val * scale + offset


def _pt(elem: PlacedElement, scale: float, tx: float, ty: float) -> tuple[float, float]:
    return _px(elem.x, scale, tx), _px(elem.y, scale, ty)


def _render_element(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    match elem.kind:
        case "line":
            return _line_svg(elem, scale, tx, ty)
        case "rect":
            return _rect_svg(elem, scale, tx, ty)
        case "wall":
            return _wall_svg(elem, scale, tx, ty)
        case "door":
            return door_svg(elem, scale, tx, ty)
        case "window":
            return window_svg(elem, scale, tx, ty)
        case "arc":
            return _arc_svg(elem, scale, tx, ty)
        case "arrow":
            return _arrow_svg(elem, scale, tx, ty)
    return ""


def _stroke(elem: PlacedElement) -> float:
    return elem.lw


def _line_svg(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    dx, dy = direction_vector(elem.direction)
    x1 = _px(elem.x, scale, tx)
    y1 = _px(elem.y, scale, ty)
    x2 = _px(elem.x + dx * elem.length, scale, tx)
    y2 = _px(elem.y + dy * elem.length, scale, ty)
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="black" stroke-width="{_stroke(elem)}"/>'
    )


def _rect_svg(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    d = elem.direction % 360
    lf = elem.length * scale   # length in px
    wf = elem.width * scale    # width in px
    ox = _px(elem.x, scale, tx)
    oy = _px(elem.y, scale, ty)

    if d == 90:    # right: top-left is origin
        rx, ry, rw, rh = ox, oy, lf, wf
    elif d == 270:  # left: element grows leftward, width goes downward
        rx, ry, rw, rh = ox - lf, oy - wf, lf, wf
    elif d == 0:   # up: length goes up, width goes right
        rx, ry, rw, rh = ox - wf / 2, oy - lf, wf, lf
    else:           # 180 down
        rx, ry, rw, rh = ox - wf / 2, oy, wf, lf

    return (
        f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" '
        f'fill="none" stroke="black" stroke-width="{_stroke(elem)}"/>'
    )


def _wall_svg(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    d = elem.direction % 360
    lf = elem.length * scale
    wf = elem.width * scale
    ox = _px(elem.x, scale, tx)
    oy = _px(elem.y, scale, ty)

    if d == 90:
        rx, ry, rw, rh = ox, oy, lf, wf
    elif d == 270:
        rx, ry, rw, rh = ox - lf, oy - wf / 2, lf, wf
    elif d == 0:
        rx, ry, rw, rh = ox - wf / 2, oy - lf, wf, lf
    else:
        rx, ry, rw, rh = ox - wf / 2, oy, wf, lf

    return (
        f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" '
        f'fill="#333" stroke="black" stroke-width="{_stroke(elem)}"/>'
    )


def _arc_svg(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    r = elem.extra.get("radius", elem.length / 2) * scale
    sweep_deg = elem.extra.get("sweep", 90)
    cx = _px(elem.x, scale, tx)
    cy = _px(elem.y, scale, ty)
    start_x = cx + r
    start_y = cy
    rad = math.radians(sweep_deg)
    end_x = cx + r * math.cos(rad)
    end_y = cy + r * math.sin(rad)
    large = 1 if sweep_deg > 180 else 0
    return (
        f'<path d="M {start_x:.1f},{start_y:.1f} A {r:.1f},{r:.1f} 0 {large},1 '
        f'{end_x:.1f},{end_y:.1f}" fill="none" stroke="black" stroke-width="{_stroke(elem)}"/>'
    )


def _arrow_svg(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    dx, dy = direction_vector(elem.direction)
    x1 = _px(elem.x, scale, tx)
    y1 = _px(elem.y, scale, ty)
    x2 = _px(elem.x + dx * elem.length, scale, tx)
    y2 = _px(elem.y + dy * elem.length, scale, ty)
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="black" stroke-width="{_stroke(elem)}" marker-end="url(#arrowhead)"/>'
    )


def _label_svg(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    anchor_map = {"left": "start", "center": "middle", "right": "end"}
    anchor = anchor_map.get(elem.extra.get("align", "left"), "start")
    x = _px(elem.x, scale, tx)
    y = _px(elem.y, scale, ty)
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" '
        f'font-size="{LABEL_FONT}" font-family="sans-serif" text-anchor="{anchor}">'
        f'{elem.label}</text>'
    )


def _label_for_rect(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    d = elem.direction % 360
    if d == 90:
        cx = _px(elem.x + elem.length / 2, scale, tx)
        cy = _px(elem.y + elem.width / 2, scale, ty)
    elif d == 270:
        cx = _px(elem.x - elem.length / 2, scale, tx)
        cy = _px(elem.y - elem.width / 2, scale, ty)
    elif d == 0:
        cx = _px(elem.x, scale, tx)
        cy = _px(elem.y - elem.length / 2, scale, ty)
    else:
        cx = _px(elem.x, scale, tx)
        cy = _px(elem.y + elem.length / 2, scale, ty)
    return (
        f'<text x="{cx:.1f}" y="{cy:.1f}" '
        f'font-size="{LABEL_FONT}" font-family="sans-serif" text-anchor="middle" '
        f'dominant-baseline="middle">{elem.label}</text>'
    )
