from dataclasses import dataclass, field


@dataclass
class DirectionDirective:
    degrees: float  # 0=up 90=right 180=down 270=left
    source_line: int = 0


@dataclass
class LineElem:
    length: float  # feet
    lw: float | None = None  # SVG user units; None = default
    begin: tuple[float, float] | None = None
    end: tuple[float, float] | None = None
    absolute: tuple[float, float] | None = None  # A= offset from canvas origin
    source_line: int = 0


@dataclass
class RectElem:
    length: float  # feet, in drawing direction
    width: float   # feet, perpendicular to drawing direction
    lw: float | None = None
    label: str | None = None
    begin: tuple[float, float] | None = None
    end: tuple[float, float] | None = None
    absolute: tuple[float, float] | None = None
    source_line: int = 0


@dataclass
class WallElem:
    length: float  # feet
    thickness: float = 0.5  # feet (default 6")
    lw: float | None = None
    begin: tuple[float, float] | None = None
    end: tuple[float, float] | None = None
    absolute: tuple[float, float] | None = None
    source_line: int = 0


@dataclass
class DoorElem:
    width: float  # feet (clear opening)
    swing: str = "right"  # left | right | in | out
    lw: float | None = None
    absolute: tuple[float, float] | None = None
    source_line: int = 0


@dataclass
class WindowElem:
    width: float  # feet
    depth: float = 0.5  # feet (default 6")
    lw: float | None = None
    absolute: tuple[float, float] | None = None
    source_line: int = 0


@dataclass
class ArcElem:
    radius: float  # feet
    sweep: float   # degrees
    lw: float | None = None
    absolute: tuple[float, float] | None = None
    source_line: int = 0


@dataclass
class ArrowElem:
    length: float  # feet
    lw: float | None = None
    absolute: tuple[float, float] | None = None
    source_line: int = 0


@dataclass
class LabelElem:
    text: str
    align: str = "left"  # left | center | right
    absolute: tuple[float, float] | None = None
    source_line: int = 0


ASTNode = (
    DirectionDirective
    | LineElem
    | RectElem
    | WallElem
    | DoorElem
    | WindowElem
    | ArcElem
    | ArrowElem
    | LabelElem
)
