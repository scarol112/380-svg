from dataclasses import dataclass, field


@dataclass
class PlacedElement:
    kind: str          # line | rect | wall | door | window | arc | arrow | label
    number: int | None # geometry elements are numbered; labels/directives are None
    x: float           # canvas origin offset (feet) to element top-left
    y: float
    length: float      # feet, in drawing direction
    width: float       # feet, perpendicular (0 for lines/arrows)
    direction: float   # drawing direction at time of placement (degrees)
    lw: float          # SVG line weight (user units)
    label: str | None
    extra: dict = field(default_factory=dict)  # element-specific extras (swing, align, etc.)
    source_line: int = 0
