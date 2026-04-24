from ..dsl.ast import (
    ASTNode, DirectionDirective, DisplayDirective, ColorDirective,
    ShowCornerXYDirective,
    LineElem, RectElem, WallElem, DoorElem, WindowElem,
    ArcElem, ArrowElem, LabelElem,
)
from ..model import PlacedElement
from .cursor import DrawingCursor, direction_vector

DEFAULT_LW = 1.0


def _fmt_dec(v: float) -> str:
    rounded = round(v, 2)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip('0')


def _lw(val: float | None) -> float:
    return DEFAULT_LW if val is None else val


class ElementPlacer:
    def __init__(self) -> None:
        self._cursor = DrawingCursor()
        self._elements: list[PlacedElement] = []
        self._elem_counter = 0
        self._canvas_origin_set = False
        self._canvas_origin: tuple[float, float] = (0.0, 0.0)
        self._show_id: bool = True
        self._show_dims: bool = True
        self._color: str = "black"
        self._show_cornerxy: bool = False

    def place_all(self, nodes: list[ASTNode]) -> list[PlacedElement]:
        for node in nodes:
            self._dispatch(node)
        return self._elements

    def _dispatch(self, node: ASTNode) -> None:
        match node:
            case DirectionDirective():
                if self._show_cornerxy and node.degrees != self._cursor.direction:
                    self._place_cornerxy()
                self._cursor.direction = node.degrees
            case ShowCornerXYDirective():
                self._show_cornerxy = node.enabled
            case DisplayDirective():
                if node.target == "elementid":
                    self._show_id = node.enabled
                else:
                    self._show_dims = node.enabled
            case ColorDirective():
                self._color = node.color
            case LineElem():
                self._place_line(node)
            case RectElem():
                self._place_rect(node)
            case WallElem():
                self._place_wall(node)
            case DoorElem():
                self._place_door(node)
            case WindowElem():
                self._place_window(node)
            case ArcElem():
                self._place_arc(node)
            case ArrowElem():
                self._place_arrow(node)
            case LabelElem():
                self._place_label(node)

    # ── coordinate helpers ────────────────────────────────────────────────────

    def _next_number(self) -> int:
        self._elem_counter += 1
        return self._elem_counter

    def _resolve_position(self, absolute: tuple[float, float] | None) -> tuple[float, float]:
        if absolute is not None:
            ox, oy = self._canvas_origin
            return ox + absolute[0], oy + absolute[1]
        return self._cursor.x, self._cursor.y

    def _set_canvas_origin_if_needed(self, x: float, y: float) -> None:
        if not self._canvas_origin_set:
            self._canvas_origin = (x, y)
            self._canvas_origin_set = True

    def _move_cursor_to_end(self, x: float, y: float, length: float) -> None:
        dx, dy = direction_vector(self._cursor.direction)
        self._cursor.x = x + dx * length
        self._cursor.y = y + dy * length

    def _flags(self) -> dict:
        return {"show_id": self._show_id, "show_dims": self._show_dims}

    def _resolve_color(self, elem_color: str | None) -> str:
        return elem_color if elem_color is not None else self._color

    # ── element placers ───────────────────────────────────────────────────────

    def _place_line(self, elem: LineElem) -> None:
        x, y = self._resolve_position(elem.absolute)
        self._set_canvas_origin_if_needed(x, y)
        self._elements.append(PlacedElement(
            kind="line", number=self._next_number(),
            x=x, y=y, length=elem.length, width=0.0,
            direction=self._cursor.direction,
            lw=_lw(elem.lw), dash=elem.dash, color=self._resolve_color(elem.color), label=None,
            **self._flags(), source_line=elem.source_line,
        ))
        self._move_cursor_to_end(x, y, elem.length)

    def _place_rect(self, elem: RectElem) -> None:
        x, y = self._resolve_position(elem.absolute)
        self._set_canvas_origin_if_needed(x, y)
        self._elements.append(PlacedElement(
            kind="rect", number=self._next_number(),
            x=x, y=y, length=elem.length, width=elem.width,
            direction=self._cursor.direction,
            lw=_lw(elem.lw), dash=elem.dash, color=self._resolve_color(elem.color), label=elem.label,
            **self._flags(), source_line=elem.source_line,
        ))
        self._move_cursor_to_end(x, y, elem.length)

    def _place_wall(self, elem: WallElem) -> None:
        x, y = self._resolve_position(elem.absolute)
        self._set_canvas_origin_if_needed(x, y)
        self._elements.append(PlacedElement(
            kind="wall", number=self._next_number(),
            x=x, y=y, length=elem.length, width=elem.thickness,
            direction=self._cursor.direction,
            lw=_lw(elem.lw), dash=elem.dash, color=self._resolve_color(elem.color), label=None,
            extra={"thickness": elem.thickness},
            **self._flags(), source_line=elem.source_line,
        ))
        self._move_cursor_to_end(x, y, elem.length)

    def _place_door(self, elem: DoorElem) -> None:
        x, y = self._resolve_position(elem.absolute)
        self._set_canvas_origin_if_needed(x, y)
        self._elements.append(PlacedElement(
            kind="door", number=self._next_number(),
            x=x, y=y, length=elem.width, width=0.0,
            direction=self._cursor.direction,
            lw=_lw(elem.lw), dash=elem.dash, color=self._resolve_color(elem.color), label=None,
            extra={"swing": elem.swing},
            **self._flags(), source_line=elem.source_line,
        ))
        self._move_cursor_to_end(x, y, elem.width)

    def _place_window(self, elem: WindowElem) -> None:
        x, y = self._resolve_position(elem.absolute)
        self._set_canvas_origin_if_needed(x, y)
        self._elements.append(PlacedElement(
            kind="window", number=self._next_number(),
            x=x, y=y, length=elem.width, width=elem.depth,
            direction=self._cursor.direction,
            lw=_lw(elem.lw), dash=elem.dash, color=self._resolve_color(elem.color), label=None,
            extra={"depth": elem.depth},
            **self._flags(), source_line=elem.source_line,
        ))
        self._move_cursor_to_end(x, y, elem.width)

    def _place_arc(self, elem: ArcElem) -> None:
        x, y = self._resolve_position(elem.absolute)
        self._set_canvas_origin_if_needed(x, y)
        self._elements.append(PlacedElement(
            kind="arc", number=self._next_number(),
            x=x, y=y, length=elem.radius * 2, width=elem.radius * 2,
            direction=self._cursor.direction,
            lw=_lw(elem.lw), dash=elem.dash, color=self._resolve_color(elem.color), label=None,
            extra={"radius": elem.radius, "sweep": elem.sweep},
            **self._flags(), source_line=elem.source_line,
        ))
        self._move_cursor_to_end(x, y, elem.radius * 2)

    def _place_arrow(self, elem: ArrowElem) -> None:
        x, y = self._resolve_position(elem.absolute)
        self._set_canvas_origin_if_needed(x, y)
        self._elements.append(PlacedElement(
            kind="arrow", number=self._next_number(),
            x=x, y=y, length=elem.length, width=0.0,
            direction=self._cursor.direction,
            lw=_lw(elem.lw), dash=elem.dash, color=self._resolve_color(elem.color), label=None,
            **self._flags(), source_line=elem.source_line,
        ))
        self._move_cursor_to_end(x, y, elem.length)

    def _place_cornerxy(self) -> None:
        x, y = self._cursor.x, self._cursor.y
        label = f"{_fmt_dec(x)}, {_fmt_dec(y)}"
        self._elements.append(PlacedElement(
            kind="cornerxy", number=None,
            x=x, y=y, length=0.0, width=0.0,
            direction=self._cursor.direction,
            lw=0.8, dash=None, color="#888", label=label,
            extra={},
        ))

    def _place_label(self, elem: LabelElem) -> None:
        x, y = self._resolve_position(elem.absolute)
        self._set_canvas_origin_if_needed(x, y)
        extra: dict = {"align": elem.align}
        if elem.font_size is not None:
            extra["font_size"] = elem.font_size
        self._elements.append(PlacedElement(
            kind="label", number=None,
            x=x, y=y, length=0.0, width=0.0,
            direction=self._cursor.direction,
            lw=DEFAULT_LW, dash=None, color="black", label=elem.text,
            extra=extra,
            source_line=elem.source_line,
        ))
