from ..model import PlacedElement
from .cursor import direction_vector

# Print area: 8×10 inches at 96 SVG units/inch
PRINT_W_PX = 768.0   # 8 inches
PRINT_H_PX = 960.0   # 10 inches
MARGIN_PX  = 48.0    # 0.5-inch margin on each side


def compute_bounding_box(elements: list[PlacedElement]) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, max_x, max_y) in feet."""
    geometry = [e for e in elements if e.kind != "label"]
    if not geometry:
        return 0.0, 0.0, 1.0, 1.0

    xs: list[float] = []
    ys: list[float] = []
    for e in geometry:
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


def compute_scale(elements: list[PlacedElement]) -> tuple[float, float, float]:
    """Return (scale_ft_to_px, translate_x_px, translate_y_px).

    translate values center the drawing within the 11×8.5in landscape page
    (1056×816 SVG units).
    """
    min_x, min_y, max_x, max_y = compute_bounding_box(elements)
    width_ft  = max_x - min_x or 1.0
    height_ft = max_y - min_y or 1.0

    usable_w = PRINT_W_PX - 2 * MARGIN_PX
    usable_h = PRINT_H_PX - 2 * MARGIN_PX

    scale = min(usable_w / width_ft, usable_h / height_ft)

    # center within full landscape page (1056×816)
    drawing_w_px = width_ft  * scale
    drawing_h_px = height_ft * scale
    tx = (1056 - drawing_w_px) / 2 - min_x * scale
    ty = (816  - drawing_h_px) / 2 - min_y * scale

    return scale, tx, ty
