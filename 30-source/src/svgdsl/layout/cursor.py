import math


# Direction degrees → (dx, dy) unit vector in SVG space (Y increases downward)
_DIR_VECTORS: dict[float, tuple[float, float]] = {
    0.0:   (0.0,  -1.0),  # up
    90.0:  (1.0,   0.0),  # right
    180.0: (0.0,   1.0),  # down
    270.0: (-1.0,  0.0),  # left
}


def direction_vector(degrees: float) -> tuple[float, float]:
    degrees = degrees % 360
    if degrees in _DIR_VECTORS:
        return _DIR_VECTORS[degrees]
    rad = math.radians(degrees)
    # 0=up means angle from Y-axis clockwise; map to SVG space
    return math.sin(rad), -math.cos(rad)


class DrawingCursor:
    def __init__(self) -> None:
        self.x: float = 0.0
        self.y: float = 0.0
        self.direction: float = 90.0  # default rightward

    def advance(self, length: float) -> None:
        dx, dy = direction_vector(self.direction)
        self.x += dx * length
        self.y += dy * length
