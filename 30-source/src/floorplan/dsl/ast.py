from dataclasses import dataclass, field


@dataclass
class DirectionDirective:
    degrees: float  # 0=up 90=right 180=down 270=left
    source_line: int = 0


@dataclass
class LineElem:
    length: float  # feet
    lw: float | None = None  # SVG user units; None = default
    dash: str | None = None
    color: str | None = None  # overrides color directive for this element
    begin: tuple[float, float] | None = None
    end: tuple[float, float] | None = None
    absolute: tuple[float, float] | None = None  # A= offset from canvas origin
    name: str | None = None
    source_line: int = 0


@dataclass
class RectElem:
    length: float  # feet, in drawing direction
    width: float   # feet, perpendicular to drawing direction
    lw: float | None = None
    dash: str | None = None
    color: str | None = None
    label: str | None = None
    begin: tuple[float, float] | None = None
    end: tuple[float, float] | None = None
    absolute: tuple[float, float] | None = None
    name: str | None = None
    source_line: int = 0


@dataclass
class WallElem:
    length: float  # feet
    thickness: float = 0.5  # feet (default 6")
    lw: float | None = None
    dash: str | None = None
    color: str | None = None
    begin: tuple[float, float] | None = None
    end: tuple[float, float] | None = None
    absolute: tuple[float, float] | None = None
    name: str | None = None
    source_line: int = 0


@dataclass
class DoorElem:
    width: float  # feet (clear opening)
    swing: str = "right"  # left | right | in | out
    lw: float | None = None
    dash: str | None = None
    color: str | None = None
    absolute: tuple[float, float] | None = None
    name: str | None = None
    source_line: int = 0


@dataclass
class WindowElem:
    width: float  # feet
    depth: float = 0.5  # feet (default 6")
    lw: float | None = None
    dash: str | None = None
    color: str | None = None
    absolute: tuple[float, float] | None = None
    name: str | None = None
    source_line: int = 0


@dataclass
class ArcElem:
    radius: float  # feet
    sweep: float   # degrees
    ccw: bool = False
    lw: float | None = None
    dash: str | None = None
    color: str | None = None
    absolute: tuple[float, float] | None = None
    name: str | None = None
    source_line: int = 0


@dataclass
class ArrowElem:
    length: float  # feet
    lw: float | None = None
    dash: str | None = None
    color: str | None = None
    absolute: tuple[float, float] | None = None
    name: str | None = None
    source_line: int = 0


@dataclass
class CircleElem:
    radius: float  # feet
    lw: float | None = None
    dash: str | None = None
    color: str | None = None
    absolute: tuple[float, float] | None = None
    name: str | None = None
    source_line: int = 0


@dataclass
class PointElem:
    lw: float | None = None  # stroke width; None = default 1px
    color: str | None = None
    absolute: tuple[float, float] | None = None
    name: str | None = None
    source_line: int = 0


@dataclass
class LabelElem:
    text: str
    align: str = "left"  # left | center | right
    font_size: float | None = None
    font_family: str | None = None
    color: str | None = None
    absolute: tuple[float, float] | None = None
    name: str | None = None
    source_line: int = 0


@dataclass
class MoveToElem:
    dest_x: float           # canvas-origin-relative feet
    dest_y: float
    absolute: tuple[float, float] | None = None  # A= start override
    source_line: int = 0


@dataclass
class LineToElem:
    dest_x: float           # canvas-origin-relative feet
    dest_y: float
    lw: float | None = None
    dash: str | None = None
    color: str | None = None
    absolute: tuple[float, float] | None = None  # A= start override
    name: str | None = None
    source_line: int = 0


@dataclass
class DisplayDirective:
    target: str   # "elementid" or "dimensions"
    enabled: bool
    source_line: int = 0


@dataclass
class ColorDirective:
    color: str     # CSS color value; "black" = reset to default
    source_line: int = 0


@dataclass
class ShowCornerXYDirective:
    enabled: bool
    source_line: int = 0


# ── text features ─────────────────────────────────────────────────────────────

@dataclass
class TextStyleDirective:
    """Global default font size and family for all subsequent text elements."""
    size: float | None = None
    font_family: str | None = None
    source_line: int = 0


@dataclass
class TextLineElem:
    """Text placed along a named element, anchored at left/center/right end."""
    text: str
    element_name: str
    align: str = "center"   # left | center | right
    font_size: float | None = None
    font_family: str | None = None
    color: str | None = None
    source_line: int = 0


@dataclass
class TextBreakElem:
    """Text centered on a named line, visually breaking it with a white border box."""
    text: str
    element_name: str
    align: str = "center"
    font_size: float | None = None
    font_family: str | None = None
    lw: float | None = None
    color: str | None = None
    source_line: int = 0


@dataclass
class TextBoxElem:
    """Explicit-size rect with text inside; advances cursor like rect."""
    length: float   # feet, in drawing direction
    width: float    # feet, perpendicular
    text: str = ""
    align: str = "left"   # left | center | right
    wrap: bool = False
    font_size: float | None = None
    font_family: str | None = None
    lw: float | None = None
    dash: str | None = None
    color: str | None = None
    absolute: tuple[float, float] | None = None
    name: str | None = None
    source_line: int = 0


@dataclass
class TextAppendElem:
    """Append a text row to a named rect/textbox, expanding it downward."""
    text: str
    element_name: str
    align: str = "left"
    font_size: float | None = None
    font_family: str | None = None
    color: str | None = None
    source_line: int = 0


ASTNode = (
    DirectionDirective
    | DisplayDirective
    | ColorDirective
    | ShowCornerXYDirective
    | TextStyleDirective
    | LineElem
    | RectElem
    | WallElem
    | DoorElem
    | WindowElem
    | ArcElem
    | ArrowElem
    | CircleElem
    | PointElem
    | LabelElem
    | MoveToElem
    | LineToElem
    | TextLineElem
    | TextBreakElem
    | TextBoxElem
    | TextAppendElem
)
