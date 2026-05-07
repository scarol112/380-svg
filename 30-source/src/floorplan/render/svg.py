"""SVG renderer.

All coordinates emitted here are in SVG user units (pixels at 96dpi).
The scale transform is applied as a pre-computation rather than an SVG
<g transform>, so stroke-width and font-size are always in screen pixels.
"""
import math
import re
import textwrap
from dataclasses import dataclass

from ..model import PlacedElement
from ..layout.cursor import direction_vector
from .dimensions import element_number_svg, dimension_label_svg, AnnotationRegistry
from .symbols import defs_svg, door_svg, window_svg
from .styles import DASH_PATTERNS, dash_attr as _dash_attr

PAGE_W = 1056  # 11in @ 96dpi
PAGE_H = 816   # 8.5in @ 96dpi

LABEL_FONT = 10  # room label inside rect

_CORNER_FONT = 9
_CORNER_LEAD_GAP = 5    # px gap from corner point to leader start
_CORNER_LEAD_LEN = 14   # px leader line length
_CORNER_TEXT_GAP = 3    # px gap from leader end to text start

# (dx, dy, text-anchor) for NE, NW, SE, SW — try in this order
_DIAGONALS: list[tuple[float, float, str]] = [
    (+0.7071, -0.7071, "start"),  # NE (preferred)
    (-0.7071, -0.7071, "end"),    # NW
    (+0.7071, +0.7071, "start"),  # SE
    (-0.7071, +0.7071, "end"),    # SW
]


_LABEL_CHAR_W = 0.47  # estimated average char width as fraction of font size
_WRAP_CHAR_W  = 0.45  # more accurate average for proportional sans-serif word-wrap
_LABEL_LINE_H = 1.4

# ── inline markup ─────────────────────────────────────────────────────────────

@dataclass
class InlineSpan:
    text: str
    bold: bool = False
    italic: bool = False


def _parse_inline_markup(raw: str) -> list[InlineSpan]:
    """Parse *italic*, **bold**, ***bold+italic***, and \\* escape into spans."""
    spans: list[InlineSpan] = []
    i = 0
    current: list[str] = []

    while i < len(raw):
        if raw[i] == '\\' and i + 1 < len(raw) and raw[i + 1] == '*':
            current.append('*')
            i += 2
            continue

        if raw[i] == '*':
            j = i
            while j < len(raw) and raw[j] == '*':
                j += 1
            star_count = j - i

            if current:
                spans.append(InlineSpan(text=''.join(current)))
                current = []

            if star_count >= 3:
                bold = italic = True
                closer = '***'
            elif star_count == 2:
                bold, italic = True, False
                closer = '**'
            else:
                bold, italic = False, True
                closer = '*'

            end = raw.find(closer, j)
            if end == -1:
                # No matching close — emit literal asterisks as plain text
                current.extend(['*'] * star_count)
                i = j
            else:
                spans.append(InlineSpan(text=raw[j:end], bold=bold, italic=italic))
                i = end + len(closer)
            continue

        current.append(raw[i])
        i += 1

    if current:
        spans.append(InlineSpan(text=''.join(current)))

    return spans or [InlineSpan(text=raw)]


def _xml_esc(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _spans_to_svg(
    spans: list[InlineSpan],
    x: float,
    y: float,
    font_size: float,
    font_family: str,
    anchor: str,
    color: str = "black",
    transform: str = "",
    dominant_baseline: str = "",
) -> str:
    """Render inline-markup spans as a <text> element with <tspan> children."""
    trans_attr = f' transform="{transform}"' if transform else ""
    base_attr = f' dominant-baseline="{dominant_baseline}"' if dominant_baseline else ""
    has_style = any(s.bold or s.italic for s in spans)

    parts: list[str] = [
        f'<text x="{x:.1f}" y="{y:.1f}" '
        f'font-size="{font_size}" font-family="{font_family}" '
        f'fill="{color}" text-anchor="{anchor}"{base_attr}{trans_attr}>'
    ]

    if not has_style and len(spans) == 1:
        parts.append(_xml_esc(spans[0].text))
    else:
        for span in spans:
            attrs: list[str] = []
            if span.bold:
                attrs.append('font-weight="bold"')
            if span.italic:
                attrs.append('font-style="italic"')
            attr_str = (' ' + ' '.join(attrs)) if attrs else ''
            parts.append(f'<tspan{attr_str}>{_xml_esc(span.text)}</tspan>')

    parts.append('</text>')
    return ''.join(parts)


def _readable_angle(direction: float) -> float:
    """Convert drawing direction to SVG rotation that keeps text uphill and readable."""
    angle = (direction - 90) % 360
    if angle > 180:
        angle -= 360  # normalize to (-180, 180]
    if abs(angle) > 90:  # text would face backwards — flip 180°
        angle = angle - 180 if angle > 0 else angle + 180
    return angle


def _plain_len(text: str) -> int:
    """Length of text after stripping inline markup characters."""
    return len(re.sub(r'\\\*|\*+', '', text))


def _wrap_text(raw: str, available_px: float, font_size: float) -> list[str]:
    """Break text into lines fitting available_px, wrapping at word boundaries."""
    chars = max(1, int(available_px / (font_size * _WRAP_CHAR_W)))
    lines = textwrap.wrap(raw, width=chars, break_long_words=True)
    return lines or [raw]


# ── bbox helpers ──────────────────────────────────────────────────────────────

def _free_label_bbox(
    elem: PlacedElement, scale: float, tx: float, ty: float
) -> tuple[float, float, float, float]:
    font_size = elem.extra.get("font_size", LABEL_FONT)
    x = _px(elem.x, scale, tx)
    y = _px(elem.y, scale, ty)
    lines = (elem.label or "").split('\n')
    w = max((_plain_len(ln) for ln in lines), default=0) * font_size * _LABEL_CHAR_W
    h = font_size * _LABEL_LINE_H * len(lines)
    align = elem.extra.get("align", "left")
    if align == "center":
        return x - w / 2, y - h, x + w / 2, y
    if align == "right":
        return x - w, y - h, x, y
    return x, y - h, x + w, y  # left


def _rect_label_bbox(
    elem: PlacedElement, scale: float, tx: float, ty: float
) -> tuple[float, float, float, float]:
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
    w = _plain_len(elem.label or "") * LABEL_FONT * _LABEL_CHAR_W
    h = LABEL_FONT * _LABEL_LINE_H
    return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2


def _corner_leader_pos(
    cx: float, cy: float, ldx: float, ldy: float
) -> tuple[float, float, float, float, float, float]:
    """Return (lx1, ly1, lx2, ly2, tax, tay) for a corner leader in direction (ldx, ldy)."""
    lx1 = cx + ldx * _CORNER_LEAD_GAP
    ly1 = cy + ldy * _CORNER_LEAD_GAP
    lx2 = cx + ldx * (_CORNER_LEAD_GAP + _CORNER_LEAD_LEN)
    ly2 = cy + ldy * (_CORNER_LEAD_GAP + _CORNER_LEAD_LEN)
    tax = lx2 + ldx * _CORNER_TEXT_GAP
    tay = ly2 + ldy * _CORNER_TEXT_GAP
    return lx1, ly1, lx2, ly2, tax, tay


def _corner_text_bbox(
    tax: float, tay: float, text: str, anchor: str
) -> tuple[float, float, float, float]:
    w = len(text) * _CORNER_FONT * 0.55
    h = _CORNER_FONT * 1.4
    x1 = tax if anchor == "start" else tax - w
    return x1, tay - h, x1 + w, tay


def _cornerxy_svg(
    elem: PlacedElement, scale: float, tx: float, ty: float, registry: AnnotationRegistry
) -> str:
    cx = _px(elem.x, scale, tx)
    cy = _px(elem.y, scale, ty)
    text = elem.label or ""

    # Pick first diagonal whose text bbox is clear of registered geometry/annotations
    chosen = _DIAGONALS[0]
    for ldx, ldy, anchor in _DIAGONALS:
        _, _, _, _, tax, tay = _corner_leader_pos(cx, cy, ldx, ldy)
        bbox = _corner_text_bbox(tax, tay, text, anchor)
        if not registry._overlaps(*bbox):
            registry.register_box(*bbox)
            chosen = (ldx, ldy, anchor)
            break
    else:
        # All directions overlapped; fall back to NE and register anyway
        ldx, ldy, anchor = _DIAGONALS[0]
        _, _, _, _, tax, tay = _corner_leader_pos(cx, cy, ldx, ldy)
        registry.register_box(*_corner_text_bbox(tax, tay, text, anchor))
        chosen = (ldx, ldy, anchor)

    ldx, ldy, anchor = chosen
    lx1, ly1, lx2, ly2, tax, tay = _corner_leader_pos(cx, cy, ldx, ldy)
    return (
        f'<line x1="{lx1:.1f}" y1="{ly1:.1f}" x2="{lx2:.1f}" y2="{ly2:.1f}" '
        f'stroke="#888" stroke-width="0.8"/>\n    '
        f'<text x="{tax:.1f}" y="{tay:.1f}" '
        f'font-size="{_CORNER_FONT}" font-family="sans-serif" fill="#888" '
        f'text-anchor="{anchor}">{text}</text>'
    )


# ── rect geometry helper ──────────────────────────────────────────────────────

def _rect_box(
    elem: PlacedElement, scale: float, tx: float, ty: float, extra_h: float = 0.0
) -> tuple[float, float, float, float]:
    """Return (rx, ry, rw, rh) in SVG pixels for a rect/wall/textbox element.

    extra_h is additional height in SVG pixels appended in the 'width' direction.
    """
    d = elem.direction % 360
    lf = elem.length * scale
    wf = elem.width * scale + extra_h
    ox = _px(elem.x, scale, tx)
    oy = _px(elem.y, scale, ty)

    if d == 90:
        return ox, oy, lf, wf
    if d == 270:
        return ox - lf, oy - wf, lf, wf
    if d == 0:
        return ox - wf / 2, oy - lf, wf, lf
    # d == 180
    return ox - wf / 2, oy, wf, lf


# ── render pipeline ───────────────────────────────────────────────────────────

def render_svg(elements: list[PlacedElement], scale: float, tx: float, ty: float) -> str:
    lines: list[str] = []
    lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{PAGE_W}" height="{PAGE_H}" '
        f'viewBox="0 0 {PAGE_W} {PAGE_H}">'
    )
    lines.append(defs_svg())
    lines.append('  <g id="drawing">')

    # Pass 1: geometry
    for elem in elements:
        if elem.lw == 0.0:
            continue  # 0px = invisible
        geom = _render_element(elem, scale, tx, ty)
        if geom:
            lines.append(f"    {geom}")

    # Pass 2: annotations — pre-register solid geometry so text avoids drawn lines.
    registry = AnnotationRegistry()
    _STROKE_KINDS = {"line", "lineto", "wall", "door", "window", "arrow", "arc", "point"}
    for elem in elements:
        if elem.lw > 0 and elem.kind in _STROKE_KINDS:
            bbox = _element_bbox_px(elem, scale, tx, ty)
            if bbox:
                registry.register_box(*bbox)

    for elem in elements:
        if elem.lw == 0.0 and elem.kind != "textbreak":
            continue
        if elem.number is not None and elem.show_id:
            lines.append(f"    {element_number_svg(elem, scale, tx, ty, registry)}")
        if elem.number is not None and elem.show_dims:
            lines.append(f"    {dimension_label_svg(elem, scale, tx, ty, registry)}")
        if elem.kind == "rect" and elem.label:
            lines.append(f"    {_label_for_rect(elem, scale, tx, ty)}")
            registry.register_box(*_rect_label_bbox(elem, scale, tx, ty))
        if elem.kind in ("rect", "textbox") and elem.extra.get("text_rows"):
            lines.append(f"    {_text_rows_svg(elem, scale, tx, ty)}")
        if elem.kind == "textbox" and elem.label:
            lines.append(f"    {_textbox_label_svg(elem, scale, tx, ty)}")
        if elem.kind == "label":
            lines.append(f"    {_label_svg(elem, scale, tx, ty)}")
            registry.register_box(*_free_label_bbox(elem, scale, tx, ty))
        if elem.kind == "textline":
            lines.append(f"    {_textline_svg(elem, scale, tx, ty)}")
        if elem.kind == "textbreak":
            lines.append(f"    {_textbreak_svg(elem, scale, tx, ty)}")

    # Corner markers last so they avoid all geometry and prior annotations
    for elem in elements:
        if elem.kind == "cornerxy":
            lines.append(f"    {_cornerxy_svg(elem, scale, tx, ty, registry)}")

    lines.append("  </g>")
    lines.append("</svg>")
    return "\n".join(lines)


def _px(val: float, scale: float, offset: float) -> float:
    return val * scale + offset


def _element_bbox_px(
    elem: PlacedElement, scale: float, tx: float, ty: float
) -> tuple[float, float, float, float] | None:
    """Return (x1, y1, x2, y2) SVG-pixel bounding box for a geometry element."""
    dx, dy = direction_vector(elem.direction)
    pdx, pdy = direction_vector((elem.direction + 90) % 360)
    x0 = _px(elem.x, scale, tx)
    y0 = _px(elem.y, scale, ty)
    lf = elem.length * scale
    wf = elem.width * scale  # may be 0 for lines/arrows

    # Build four corners: start, end-of-length, width-offset, both
    pts_x = [x0, x0 + dx * lf, x0 + pdx * wf, x0 + dx * lf + pdx * wf]
    pts_y = [y0, y0 + dy * lf, y0 + pdy * wf, y0 + dy * lf + pdy * wf]

    # For doors also include the arc extent (radius = door width in both directions)
    if elem.kind == "door":
        r = elem.length * scale  # door width is stored in length
        pts_x += [x0 - r, x0 + r]
        pts_y += [y0 - r, y0 + r]

    # For points, the circle radius (1.5px) plus half stroke dominates over length/width
    if elem.kind == "point":
        r = 1.5 + elem.lw / 2
        return x0 - r, y0 - r, x0 + r, y0 + r

    pad = max(elem.lw, 1.0)
    return min(pts_x) - pad, min(pts_y) - pad, max(pts_x) + pad, max(pts_y) + pad


def _render_element(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    match elem.kind:
        case "line" | "lineto":
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
        case "point":
            return _point_svg(elem, scale, tx, ty)
        case "textbox":
            return _textbox_border_svg(elem, scale, tx, ty)
    return ""


def _point_svg(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    cx = _px(elem.x, scale, tx)
    cy = _px(elem.y, scale, ty)
    return (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="1.5" '
        f'fill="{elem.color}" stroke="{elem.color}" stroke-width="{elem.lw}"/>'
    )


def _line_svg(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    dx, dy = direction_vector(elem.direction)
    x1 = _px(elem.x, scale, tx)
    y1 = _px(elem.y, scale, ty)
    x2 = _px(elem.x + dx * elem.length, scale, tx)
    y2 = _px(elem.y + dy * elem.length, scale, ty)
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{elem.color}" stroke-width="{elem.lw}"{_dash_attr(elem.dash)}/>'
    )


def _rect_svg(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    rows_h = sum(
        r["font_size"] * _LABEL_LINE_H * len(r["text"].split('\n'))
        for r in elem.extra.get("text_rows", [])
    )
    rx, ry, rw, rh = _rect_box(elem, scale, tx, ty, extra_h=rows_h)
    return (
        f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" '
        f'fill="none" stroke="{elem.color}" stroke-width="{elem.lw}"{_dash_attr(elem.dash)}/>'
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
        rx, ry, rw, rh = ox - lf, oy - wf / 2, lf, wf  # centered on cursor path
    elif d == 0:
        rx, ry, rw, rh = ox - wf / 2, oy - lf, wf, lf
    else:
        rx, ry, rw, rh = ox - wf / 2, oy, wf, lf

    return (
        f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw:.1f}" height="{rh:.1f}" '
        f'fill="#333" stroke="{elem.color}" stroke-width="{elem.lw}"{_dash_attr(elem.dash)}/>'
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
        f'{end_x:.1f},{end_y:.1f}" fill="none" stroke="{elem.color}" stroke-width="{elem.lw}"'
        f'{_dash_attr(elem.dash)}/>'
    )


def _arrow_svg(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    dx, dy = direction_vector(elem.direction)
    x1 = _px(elem.x, scale, tx)
    y1 = _px(elem.y, scale, ty)
    x2 = _px(elem.x + dx * elem.length, scale, tx)
    y2 = _px(elem.y + dy * elem.length, scale, ty)
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{elem.color}" stroke-width="{elem.lw}" marker-end="url(#arrowhead)"'
        f'{_dash_attr(elem.dash)}/>'
    )


# ── text rendering ────────────────────────────────────────────────────────────

def _label_svg(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    anchor_map = {"left": "start", "center": "middle", "right": "end"}
    anchor = anchor_map.get(elem.extra.get("align", "left"), "start")
    font_size = elem.extra.get("font_size", LABEL_FONT)
    font_family = elem.extra.get("font_family", "sans-serif")
    x = _px(elem.x, scale, tx)
    y = _px(elem.y, scale, ty)
    lines = (elem.label or "").split('\n')
    parts = []
    for i, line in enumerate(lines):
        y_pos = y + i * font_size * _LABEL_LINE_H
        if line:
            spans = _parse_inline_markup(line)
            parts.append(_spans_to_svg(spans, x, y_pos, font_size, font_family,
                                       anchor, color=elem.color))
        # blank lines advance y but produce no element
    return "\n    ".join(parts) if parts else ""


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
    font_family = elem.extra.get("font_family", "sans-serif")
    spans = _parse_inline_markup(elem.label or "")
    return _spans_to_svg(spans, cx, cy, LABEL_FONT, font_family, "middle",
                         dominant_baseline="central")


def _textbox_text_width_px(elem: PlacedElement, scale: float) -> float:
    """Horizontal text-area width of a textbox in SVG pixels."""
    d = elem.direction % 360
    return elem.length * scale if d in (90, 270) else elem.width * scale


def _textbox_content_height_px(elem: PlacedElement, rw: float) -> float:
    """Pixel height occupied by the textbox's main label after word-wrapping."""
    if not elem.label:
        return 0.0
    font_size = elem.extra.get("font_size", LABEL_FONT)
    available = rw - 2 * (font_size * 0.4)  # subtract actual left+right margins
    count = 0
    for para in (elem.label or "").split('\n'):
        if para:
            count += len(_wrap_text(para, available, font_size))
        else:
            count += 1  # blank-line spacer
    return count * font_size * _LABEL_LINE_H


def _textbox_rows_height_px(elem: PlacedElement, rw: float = 0.0) -> float:
    """Height of textappend rows. Pass rw>0 for word-wrap-aware counting."""
    total = 0.0
    for r in elem.extra.get("text_rows", []):
        fs = r["font_size"]
        available = rw - 2 * (fs * 0.4) if rw > 0 else 0.0
        for sub_line in r["text"].split('\n'):
            if sub_line and available > 0:
                total += fs * _LABEL_LINE_H * len(_wrap_text(sub_line, available, fs))
            else:
                total += fs * _LABEL_LINE_H
    return total


def _textbox_border_svg(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    rw = _textbox_text_width_px(elem, scale)
    content_h = _textbox_content_height_px(elem, rw)
    initial_h = elem.width * scale
    rows_h = _textbox_rows_height_px(elem, rw)
    # Border is at least initial_h; grows if content + appended rows need more space.
    extra_h = max(0.0, content_h + rows_h - initial_h)
    rx, ry, rw_box, rh = _rect_box(elem, scale, tx, ty, extra_h=extra_h)
    return (
        f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{rw_box:.1f}" height="{rh:.1f}" '
        f'fill="none" stroke="{elem.color}" stroke-width="{elem.lw}"{_dash_attr(elem.dash)}/>'
    )


def _textbox_label_svg(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    """Render the main label text inside a textbox, always word-wrapped."""
    font_size = elem.extra.get("font_size", LABEL_FONT)
    font_family = elem.extra.get("font_family", "sans-serif")
    align = elem.extra.get("align", "left")
    anchor_map = {"left": "start", "center": "middle", "right": "end"}
    anchor = anchor_map.get(align, "start")

    rx, ry, rw, _ = _rect_box(elem, scale, tx, ty)
    x_margin = font_size * 0.4

    if align == "left":
        text_x = rx + x_margin
    elif align == "right":
        text_x = rx + rw - x_margin
    else:
        text_x = rx + rw / 2

    # Split on explicit \n, then word-wrap each non-empty paragraph.
    available = rw - 2 * x_margin  # actual usable text width
    all_lines: list[str] = []
    for para in (elem.label or "").split('\n'):
        if para:
            all_lines.extend(_wrap_text(para, available, font_size))
        else:
            all_lines.append('')  # blank-line spacer

    parts: list[str] = []
    for i, line in enumerate(all_lines):
        y_pos = ry + font_size * (1 + i * _LABEL_LINE_H)
        if line:
            spans = _parse_inline_markup(line)
            parts.append(_spans_to_svg(spans, text_x, y_pos, font_size, font_family,
                                       anchor, color=elem.color))
    return "\n    ".join(parts)


def _text_rows_svg(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    """Render textappend rows below a rect or textbox."""
    text_rows = elem.extra.get("text_rows", [])
    if not text_rows:
        return ""

    rx, ry, rw, rh_base = _rect_box(elem, scale, tx, ty)
    anchor_map = {"left": "start", "center": "middle", "right": "end"}

    # For textbox: rows follow immediately after the text content (inside the rect).
    # For rect: rows follow after the fixed initial height (below the rect border).
    if elem.kind == "textbox" and elem.label:
        rw_text = _textbox_text_width_px(elem, scale)
        content_h = _textbox_content_height_px(elem, rw_text)
        row_top = ry + content_h
    else:
        row_top = ry + rh_base

    parts: list[str] = []
    for row in text_rows:
        fs = row["font_size"]
        row_align = row.get("align", "left")
        anchor = anchor_map.get(row_align, "start")
        x_margin = fs * 0.4
        available = rw - 2 * x_margin
        if row_align == "left":
            row_x = rx + x_margin
        elif row_align == "right":
            row_x = rx + rw - x_margin
        else:
            row_x = rx + rw / 2
        font_family = row.get("font_family", "sans-serif")
        color = row.get("color", "black")
        for sub_line in row["text"].split('\n'):
            if sub_line:
                wrapped = _wrap_text(sub_line, available, fs) if elem.kind == "textbox" else [sub_line]
                for wline in wrapped:
                    baseline = row_top + fs
                    spans = _parse_inline_markup(wline)
                    parts.append(_spans_to_svg(spans, row_x, baseline, fs,
                                               font_family, anchor, color=color))
                    row_top += fs * _LABEL_LINE_H
            else:
                row_top += fs * _LABEL_LINE_H

    return "\n    ".join(parts)


def _textline_svg(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    """Render text along a line (rotated to match its direction)."""
    align = elem.extra.get("align", "center")
    font_size = elem.extra.get("font_size", LABEL_FONT)
    font_family = elem.extra.get("font_family", "sans-serif")
    anchor_map = {"left": "start", "center": "middle", "right": "end"}
    anchor = anchor_map.get(align, "middle")

    dx, dy = direction_vector(elem.direction)
    x0 = _px(elem.x, scale, tx)
    y0 = _px(elem.y, scale, ty)

    if align == "left":
        ax, ay = x0, y0
    elif align == "right":
        ax = _px(elem.x + dx * elem.length, scale, tx)
        ay = _px(elem.y + dy * elem.length, scale, ty)
    else:
        ax = _px(elem.x + dx * elem.length / 2, scale, tx)
        ay = _px(elem.y + dy * elem.length / 2, scale, ty)

    # Offset text slightly above the line (perpendicular direction)
    pdx, pdy = direction_vector((elem.direction + 270) % 360)  # 90° left = above for dir=90
    offset_px = font_size * 0.5
    ax += pdx * offset_px
    ay += pdy * offset_px

    angle = _readable_angle(elem.direction)
    transform = f"rotate({angle:.1f},{ax:.1f},{ay:.1f})" if angle != 0.0 else ""

    spans = _parse_inline_markup(elem.label or "")
    return _spans_to_svg(spans, ax, ay, font_size, font_family, anchor,
                         color=elem.color, transform=transform)


def _textbreak_svg(elem: PlacedElement, scale: float, tx: float, ty: float) -> str:
    """Text centered on a line with a white fill box obscuring the line behind it."""
    align = elem.extra.get("align", "center")
    font_size = elem.extra.get("font_size", LABEL_FONT)
    font_family = elem.extra.get("font_family", "sans-serif")

    dx, dy = direction_vector(elem.direction)
    x0 = _px(elem.x, scale, tx)
    y0 = _px(elem.y, scale, ty)

    raw_len = _plain_len(elem.label or "")
    text_w = raw_len * font_size * _LABEL_CHAR_W
    text_h = font_size * _LABEL_LINE_H
    pad = 4
    box_h = text_h + pad * 2
    box_w = text_w + pad * 2

    # Work in line-local coordinates (u=0 at line start, u=L at line end).
    # For left/right alignment, leave 6px of the near tip visible.
    L = elem.length * scale
    if align == "left":
        u_left = 6
        u_right = u_left + box_w
    elif align == "right":
        u_right = L - 6
        u_left = u_right - box_w
    else:
        u_left = L / 2 - box_w / 2
        u_right = L / 2 + box_w / 2

    center_u = (u_left + u_right) / 2

    # Convert local centre to screen coordinates
    ax = x0 + dx * center_u
    ay = y0 + dy * center_u
    rx = ax - box_w / 2
    ry = ay - box_h / 2

    angle = _readable_angle(elem.direction)
    trans = f"rotate({angle:.1f},{ax:.1f},{ay:.1f})" if angle != 0.0 else ""
    ta = f' transform="{trans}"' if trans else ""

    # Text baseline: roughly center of box
    ty_pos = ay + font_size * 0.35

    parts = [
        f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{box_w:.1f}" height="{box_h:.1f}" '
        f'fill="white"{ta}/>',
    ]
    if elem.lw > 0:
        parts.append(
            f'<rect x="{rx:.1f}" y="{ry:.1f}" width="{box_w:.1f}" height="{box_h:.1f}" '
            f'fill="none" stroke="{elem.color}" stroke-width="{elem.lw}"{ta}/>'
        )
    spans = _parse_inline_markup(elem.label or "")
    parts.append(_spans_to_svg(spans, ax, ty_pos, font_size, font_family,
                               "middle", color=elem.color, transform=trans))
    return "\n    ".join(parts)
