from ..model import PlacedElement
from ..layout.cursor import direction_vector

NUM_FONT = 10   # 8 × 1.2 (+10% then +20% = net +32%)
DIM_FONT = 11   # 9 × 1.2
OFFSET_PX = 12  # clearance beyond element outer edge

_CHAR_WIDTH_RATIO = 0.55
_LINE_HEIGHT_RATIO = 1.4


def _fmt_feet(ft: float) -> str:
    total_inches = round(ft * 12)
    feet, inches = divmod(total_inches, 12)
    if feet == 0:
        return f'{inches}"'
    if inches == 0:
        return f"{feet}'"
    return f"{feet}'{inches}\""


def _px(val: float, scale: float, offset: float) -> float:
    return val * scale + offset


def _text_bbox(cx: float, cy: float, text: str, font_size: float) -> tuple[float, float, float, float]:
    """(x1, y1, x2, y2) for centre-anchored text baseline at (cx, cy)."""
    w = len(text) * font_size * _CHAR_WIDTH_RATIO
    h = font_size * _LINE_HEIGHT_RATIO
    return cx - w / 2, cy - h, cx + w / 2, cy


class AnnotationRegistry:
    """Tracks occupied bounding boxes (geometry + placed text) to resolve overlaps."""

    def __init__(self) -> None:
        self._boxes: list[tuple[float, float, float, float]] = []

    def register_box(self, x1: float, y1: float, x2: float, y2: float) -> None:
        self._boxes.append((x1, y1, x2, y2))

    def _overlaps(self, x1: float, y1: float, x2: float, y2: float) -> bool:
        for bx1, by1, bx2, by2 in self._boxes:
            if x1 < bx2 and x2 > bx1 and y1 < by2 and y2 > by1:
                return True
        return False

    def place(
        self,
        cx: float,
        cy: float,
        text: str,
        font_size: float,
        nudge_dx: float = 0.0,
        nudge_dy: float = 1.0,
    ) -> tuple[float, float]:
        """Find a non-overlapping position for text centred near (cx, cy).

        Nudges in (nudge_dx, nudge_dy) increments until clear or limit reached.
        Registers the chosen bounding box before returning.
        """
        step = font_size * _LINE_HEIGHT_RATIO
        # Ensure we can always nudge somewhere
        if nudge_dx == 0.0 and nudge_dy == 0.0:
            nudge_dy = 1.0
        # For purely horizontal nudge (nudge_dy=0), i=0 stays in place — start at i=0
        # is intentional (try base position first)
        for i in range(12):
            tx = cx + nudge_dx * step * i
            ty = cy + nudge_dy * step * i
            x1, y1, x2, y2 = _text_bbox(tx, ty, text, font_size)
            if not self._overlaps(x1, y1, x2, y2):
                self._boxes.append((x1, y1, x2, y2))
                return tx, ty
        # Fallback
        tx = cx + nudge_dx * step * 4
        ty = cy + nudge_dy * step * 4
        self._boxes.append(_text_bbox(tx, ty, text, font_size))
        return tx, ty


def element_number_svg(
    elem: PlacedElement,
    scale: float,
    tx: float,
    ty: float,
    registry: AnnotationRegistry,
) -> str:
    # Place number at element start, offset perpendicular toward top/left (away from body)
    perp_dx, perp_dy = direction_vector((elem.direction - 90) % 360)
    base_x = _px(elem.x, scale, tx) + perp_dx * OFFSET_PX
    base_y = _px(elem.y, scale, ty) + perp_dy * OFFSET_PX
    text = str(elem.number)
    cx, cy = registry.place(base_x, base_y, text, NUM_FONT,
                            nudge_dx=perp_dx, nudge_dy=perp_dy)
    return (
        f'<text x="{cx:.1f}" y="{cy:.1f}" '
        f'font-size="{NUM_FONT}" font-family="sans-serif" fill="red" '
        f'text-anchor="middle">{text}</text>'
    )


def dimension_label_svg(
    elem: PlacedElement,
    scale: float,
    tx: float,
    ty: float,
    registry: AnnotationRegistry,
) -> str:
    dx, dy = direction_vector(elem.direction)
    perp_dx, perp_dy = direction_vector((elem.direction + 90) % 360)

    # Start from the OUTER EDGE of the element in the perpendicular direction,
    # then add clearance. This ensures annotations land outside the element body.
    outer_x = _px(elem.x + dx * elem.length / 2 + perp_dx * elem.width, scale, tx)
    outer_y = _px(elem.y + dy * elem.length / 2 + perp_dy * elem.width, scale, ty)
    base_x = outer_x + perp_dx * OFFSET_PX
    base_y = outer_y + perp_dy * OFFSET_PX

    if elem.width > 0 and elem.kind != "window":
        dim_text = f"{_fmt_feet(elem.length)} \u00d7 {_fmt_feet(elem.width)}"
    else:
        dim_text = _fmt_feet(elem.length)

    cx, cy = registry.place(base_x, base_y, dim_text, DIM_FONT,
                            nudge_dx=perp_dx, nudge_dy=perp_dy)
    return (
        f'<text x="{cx:.1f}" y="{cy:.1f}" '
        f'font-size="{DIM_FONT}" font-family="sans-serif" fill="#555" '
        f'text-anchor="middle">{dim_text}</text>'
    )
