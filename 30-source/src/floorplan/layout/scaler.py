from ..model import PlacedElement
from .cursor import direction_vector

# Print area: full page (11×8.5in landscape) at 96 SVG units/inch, with 0.5in margin
PRINT_W_PX = 1056.0  # 11 inches
PRINT_H_PX = 816.0   # 8.5 inches
MARGIN_PX  = 48.0    # 0.5-inch margin on each side

# Mirror of cornerxy annotation geometry from render/svg.py — keep in sync.
_CXY_FONT_PX       = 9.0
_CXY_LEAD_TOTAL_PX = 22.0   # LEAD_GAP(5) + LEAD_LEN(14) + TEXT_GAP(3)
_CXY_CHAR_W        = 0.55
_CXY_LINE_H        = 1.4
_CXY_DIAG          = 0.7071


def compute_bounding_box(elements: list[PlacedElement]) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, max_x, max_y) in feet."""
    geometry = [e for e in elements if e.kind != "label"]
    if not geometry:
        return 0.0, 0.0, 1.0, 1.0

    xs: list[float] = []
    ys: list[float] = []
    for e in geometry:
        if e.kind == "circle":
            r = e.length / 2  # length stores diameter
            xs.extend([e.x - r, e.x + r])
            ys.extend([e.y - r, e.y + r])
            continue
        dx, dy = direction_vector(e.direction)
        # leading edge endpoint
        ex = e.x + dx * e.length
        ey = e.y + dy * e.length
        # perpendicular extent for rect/wall/window
        if e.width > 0:
            perp_dx, perp_dy = direction_vector((e.direction + 90) % 360)
            xs.extend([e.x, ex, e.x + perp_dx * e.width, ex + perp_dx * e.width])
            ys.extend([e.y, ey, e.y + perp_dy * e.width, ey + perp_dy * e.width])
        else:
            xs.extend([e.x, ex])
            ys.extend([e.y, ey])

    return min(xs), min(ys), max(xs), max(ys)


def _cornerxy_max_extent_px(label: str) -> tuple[float, float]:
    """Worst-case pixel extent of a cornerxy annotation from its corner point.

    Returns (max_dx_px, max_dy_px) — the farthest the leader+text can reach
    in the x and y directions, assuming the most space-consuming diagonal.
    """
    text_w = len(label) * _CXY_FONT_PX * _CXY_CHAR_W
    text_h = _CXY_FONT_PX * _CXY_LINE_H
    return _CXY_DIAG * _CXY_LEAD_TOTAL_PX + text_w, _CXY_DIAG * _CXY_LEAD_TOTAL_PX + text_h


def _scale_from_bounds(
    min_x: float, min_y: float, max_x: float, max_y: float,
    page_w: float = PRINT_W_PX, page_h: float = PRINT_H_PX,
) -> tuple[float, float, float]:
    width_ft  = max_x - min_x or 1.0
    height_ft = max_y - min_y or 1.0
    usable_w  = page_w - 2 * MARGIN_PX
    usable_h  = page_h - 2 * MARGIN_PX
    scale = min(usable_w / width_ft, usable_h / height_ft)
    drawing_w_px = width_ft  * scale
    drawing_h_px = height_ft * scale
    tx = (page_w - drawing_w_px) / 2 - min_x * scale
    ty = (page_h - drawing_h_px) / 2 - min_y * scale
    return scale, tx, ty


def compute_scale(
    elements: list[PlacedElement],
    page_w: float = PRINT_W_PX,
    page_h: float = PRINT_H_PX,
) -> tuple[float, float, float]:
    """Return (scale_ft_to_px, translate_x_px, translate_y_px).

    translate values center the drawing within the given page dimensions
    (default 11×8.5in landscape = 1056×816 SVG units at 96 dpi).
    """
    min_x, min_y, max_x, max_y = compute_bounding_box(elements)

    corners = [e for e in elements if e.kind == "cornerxy"]
    if corners:
        # Iteratively expand the bbox until the scale stabilises.  Each
        # iteration converts the fixed pixel extents of the leader+text to
        # feet using the current scale estimate; a smaller scale means the
        # annotations need more feet, so the loop converges from above.
        # Typically converges in ≤ 5 iterations (ratio ~0.93 per step).
        prev_s = None
        for _ in range(10):
            s, _, _ = _scale_from_bounds(min_x, min_y, max_x, max_y, page_w, page_h)
            if prev_s is not None and abs(s - prev_s) < 0.01:
                break
            prev_s = s
            for e in corners:
                dx_px, dy_px = _cornerxy_max_extent_px(e.label or "")
                min_x = min(min_x, e.x - dx_px / s)
                max_x = max(max_x, e.x + dx_px / s)
                min_y = min(min_y, e.y - dy_px / s)
                max_y = max(max_y, e.y + dy_px / s)

    return _scale_from_bounds(min_x, min_y, max_x, max_y, page_w, page_h)
