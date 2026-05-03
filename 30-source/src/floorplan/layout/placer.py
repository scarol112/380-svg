import math

from ..dsl.ast import (
    ASTNode, DirectionDirective, DisplayDirective, ColorDirective,
    ShowCornerXYDirective,
    LineElem, RectElem, WallElem, DoorElem, WindowElem,
    ArcElem, ArrowElem, PointElem, LabelElem,
    MoveToElem, LineToElem,
    TextStyleDirective, TextLineElem, TextBreakElem, TextBoxElem, TextAppendElem,
)
from ..dsl.parser import ParseError
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
        self._mltodir: float = 0.0
        self._named_elements: dict[str, PlacedElement] = {}
        self._text_style: dict = {"size": 10.0, "font_family": "sans-serif"}

    def place_all(self, nodes: list[ASTNode]) -> list[PlacedElement]:
        for node in nodes:
            self._dispatch(node)
        return self._elements

    def _dispatch(self, node: ASTNode) -> None:
        match node:
            case DirectionDirective():
                if self._show_cornerxy and node.degrees != self._cursor.direction:
                    self._emit_cornerxy(self._cursor.x, self._cursor.y)
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
            case TextStyleDirective():
                self._handle_textstyle(node)
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
            case PointElem():
                self._place_point(node)
            case LabelElem():
                self._place_label(node)
            case MoveToElem():
                self._place_moveto(node)
            case LineToElem():
                self._place_lineto(node)
            case TextLineElem():
                self._place_textline(node)
            case TextBreakElem():
                self._place_textbreak(node)
            case TextBoxElem():
                self._place_textbox(node)
            case TextAppendElem():
                self._place_textappend(node)

    # ── coordinate helpers ────────────────────────────────────────────────────

    def _next_number(self) -> int:
        self._elem_counter += 1
        return self._elem_counter

    def _resolve_position(self, absolute: tuple[float, float] | None) -> tuple[float, float]:
        if absolute is not None:
            ox, oy = self._canvas_origin
            return ox + absolute[0], oy + absolute[1]
        return self._cursor.x, self._cursor.y

    def _set_canvas_origin_if_needed(
        self, x: float, y: float, has_absolute: bool = False
    ) -> None:
        if not self._canvas_origin_set:
            # When the first element uses A=, the A= coordinate is already
            # relative to an implied (0,0) origin.  Setting the origin to the
            # resolved position would corrupt all subsequent A= values.
            self._canvas_origin = (0.0, 0.0) if has_absolute else (x, y)
            self._canvas_origin_set = True

    def _place_start(self, absolute: tuple[float, float] | None) -> tuple[float, float]:
        """Resolve element position and establish canvas origin on first call."""
        x, y = self._resolve_position(absolute)
        self._set_canvas_origin_if_needed(x, y, has_absolute=absolute is not None)
        return x, y

    def _move_cursor_to_end(self, x: float, y: float, length: float) -> None:
        dx, dy = direction_vector(self._cursor.direction)
        self._cursor.x = x + dx * length
        self._cursor.y = y + dy * length

    def _flags(self) -> dict:
        return {"show_id": self._show_id, "show_dims": self._show_dims}

    def _resolve_color(self, elem_color: str | None) -> str:
        return elem_color if elem_color is not None else self._color

    def _register_name(self, pe: PlacedElement, name: str | None) -> None:
        if name:
            self._named_elements[name] = pe

    def _text_font_size(self, override: float | None) -> float:
        return override if override is not None else self._text_style["size"]

    def _text_font_family(self, override: str | None) -> str:
        return override if override is not None else self._text_style["font_family"]

    # ── directive handlers ────────────────────────────────────────────────────

    def _handle_textstyle(self, elem: TextStyleDirective) -> None:
        if elem.size is not None:
            self._text_style["size"] = elem.size
        if elem.font_family is not None:
            self._text_style["font_family"] = elem.font_family

    # ── element placers ───────────────────────────────────────────────────────

    def _place_line(self, elem: LineElem) -> None:
        x, y = self._place_start(elem.absolute)
        pe = PlacedElement(
            kind="line", number=self._next_number(),
            x=x, y=y, length=elem.length, width=0.0,
            direction=self._cursor.direction,
            lw=_lw(elem.lw), dash=elem.dash, color=self._resolve_color(elem.color), label=None,
            **self._flags(), source_line=elem.source_line,
        )
        self._elements.append(pe)
        self._register_name(pe, elem.name)
        self._move_cursor_to_end(x, y, elem.length)

    def _place_rect(self, elem: RectElem) -> None:
        x, y = self._place_start(elem.absolute)
        pe = PlacedElement(
            kind="rect", number=self._next_number(),
            x=x, y=y, length=elem.length, width=elem.width,
            direction=self._cursor.direction,
            lw=_lw(elem.lw), dash=elem.dash, color=self._resolve_color(elem.color), label=elem.label,
            **self._flags(), source_line=elem.source_line,
        )
        self._elements.append(pe)
        self._register_name(pe, elem.name)
        self._move_cursor_to_end(x, y, elem.length)

    def _place_wall(self, elem: WallElem) -> None:
        x, y = self._place_start(elem.absolute)
        pe = PlacedElement(
            kind="wall", number=self._next_number(),
            x=x, y=y, length=elem.length, width=elem.thickness,
            direction=self._cursor.direction,
            lw=_lw(elem.lw), dash=elem.dash, color=self._resolve_color(elem.color), label=None,
            extra={"thickness": elem.thickness},
            **self._flags(), source_line=elem.source_line,
        )
        self._elements.append(pe)
        self._register_name(pe, elem.name)
        self._move_cursor_to_end(x, y, elem.length)

    def _place_door(self, elem: DoorElem) -> None:
        x, y = self._place_start(elem.absolute)
        pe = PlacedElement(
            kind="door", number=self._next_number(),
            x=x, y=y, length=elem.width, width=0.0,
            direction=self._cursor.direction,
            lw=_lw(elem.lw), dash=elem.dash, color=self._resolve_color(elem.color), label=None,
            extra={"swing": elem.swing},
            **self._flags(), source_line=elem.source_line,
        )
        self._elements.append(pe)
        self._register_name(pe, elem.name)
        self._move_cursor_to_end(x, y, elem.width)

    def _place_window(self, elem: WindowElem) -> None:
        x, y = self._place_start(elem.absolute)
        pe = PlacedElement(
            kind="window", number=self._next_number(),
            x=x, y=y, length=elem.width, width=elem.depth,
            direction=self._cursor.direction,
            lw=_lw(elem.lw), dash=elem.dash, color=self._resolve_color(elem.color), label=None,
            extra={"depth": elem.depth},
            **self._flags(), source_line=elem.source_line,
        )
        self._elements.append(pe)
        self._register_name(pe, elem.name)
        self._move_cursor_to_end(x, y, elem.width)

    def _place_arc(self, elem: ArcElem) -> None:
        x, y = self._place_start(elem.absolute)
        pe = PlacedElement(
            kind="arc", number=self._next_number(),
            x=x, y=y, length=elem.radius * 2, width=elem.radius * 2,
            direction=self._cursor.direction,
            lw=_lw(elem.lw), dash=elem.dash, color=self._resolve_color(elem.color), label=None,
            extra={"radius": elem.radius, "sweep": elem.sweep},
            **self._flags(), source_line=elem.source_line,
        )
        self._elements.append(pe)
        self._register_name(pe, elem.name)
        self._move_cursor_to_end(x, y, elem.radius * 2)

    def _place_arrow(self, elem: ArrowElem) -> None:
        x, y = self._place_start(elem.absolute)
        pe = PlacedElement(
            kind="arrow", number=self._next_number(),
            x=x, y=y, length=elem.length, width=0.0,
            direction=self._cursor.direction,
            lw=_lw(elem.lw), dash=elem.dash, color=self._resolve_color(elem.color), label=None,
            **self._flags(), source_line=elem.source_line,
        )
        self._elements.append(pe)
        self._register_name(pe, elem.name)
        self._move_cursor_to_end(x, y, elem.length)

    def _emit_cornerxy(self, x: float, y: float) -> None:
        self._elements.append(PlacedElement(
            kind="cornerxy", number=None,
            x=x, y=y, length=0.0, width=0.0,
            direction=self._cursor.direction,
            lw=0.8, dash=None, color="#888",
            label=f"{_fmt_dec(x)}, {_fmt_dec(y)}",
            extra={},
        ))

    def _place_point(self, elem: PointElem) -> None:
        x, y = self._place_start(elem.absolute)
        lw = elem.lw if elem.lw is not None else 1.0
        pe = PlacedElement(
            kind="point", number=self._next_number(),
            x=x, y=y, length=0.0, width=0.0,
            direction=self._cursor.direction,
            lw=lw, dash=None, color=self._resolve_color(elem.color), label=None,
            show_id=self._show_id, show_dims=False, source_line=elem.source_line,
        )
        self._elements.append(pe)
        self._register_name(pe, elem.name)
        # cursor does not advance — point marks a location without disrupting flow
        if self._show_cornerxy:
            self._emit_cornerxy(x, y)

    def _place_label(self, elem: LabelElem) -> None:
        x, y = self._place_start(elem.absolute)
        extra: dict = {"align": elem.align}
        if elem.font_size is not None:
            extra["font_size"] = elem.font_size
        if elem.font_family is not None:
            extra["font_family"] = elem.font_family
        pe = PlacedElement(
            kind="label", number=None,
            x=x, y=y, length=0.0, width=0.0,
            direction=self._cursor.direction,
            lw=DEFAULT_LW, dash=None, color="black", label=elem.text,
            extra=extra,
            source_line=elem.source_line,
        )
        self._elements.append(pe)
        self._register_name(pe, elem.name)

    def _place_moveto(self, elem: MoveToElem) -> None:
        ox, oy = self._canvas_origin
        if elem.absolute is not None:
            start_x = ox + elem.absolute[0]
            start_y = oy + elem.absolute[1]
        else:
            start_x = self._cursor.x
            start_y = self._cursor.y
        dest_x = ox + elem.dest_x
        dest_y = oy + elem.dest_y
        ddx = dest_x - start_x
        ddy = dest_y - start_y
        if ddx != 0.0 or ddy != 0.0:
            self._mltodir = math.degrees(math.atan2(ddx, -ddy)) % 360
        self._cursor.x = dest_x
        self._cursor.y = dest_y

    def _place_lineto(self, elem: LineToElem) -> None:
        ox, oy = self._canvas_origin
        if elem.absolute is not None:
            start_x = ox + elem.absolute[0]
            start_y = oy + elem.absolute[1]
        else:
            start_x = self._cursor.x
            start_y = self._cursor.y
        dest_x = ox + elem.dest_x
        dest_y = oy + elem.dest_y
        self._set_canvas_origin_if_needed(start_x, start_y, has_absolute=elem.absolute is not None)
        ddx = dest_x - start_x
        ddy = dest_y - start_y
        if ddx != 0.0 or ddy != 0.0:
            bearing = math.degrees(math.atan2(ddx, -ddy)) % 360
        else:
            bearing = self._cursor.direction
        self._mltodir = bearing
        length = math.sqrt(ddx * ddx + ddy * ddy)
        pe = PlacedElement(
            kind="lineto", number=self._next_number(),
            x=start_x, y=start_y, length=length, width=0.0,
            direction=bearing,
            lw=_lw(elem.lw), dash=elem.dash, color=self._resolve_color(elem.color), label=None,
            **self._flags(), source_line=elem.source_line,
        )
        self._elements.append(pe)
        self._register_name(pe, elem.name)
        self._cursor.x = dest_x
        self._cursor.y = dest_y

    # ── text element placers ──────────────────────────────────────────────────

    def _place_textline(self, elem: TextLineElem) -> None:
        target = self._named_elements.get(elem.element_name)
        if target is None:
            raise ParseError(
                f"Line {elem.source_line}: textline: element '{elem.element_name}' not found"
            )
        # Bake the reference element's geometry into this PlacedElement so the
        # renderer needs no lookup at draw time.
        pe = PlacedElement(
            kind="textline", number=None,
            x=target.x, y=target.y,
            length=target.length, width=0.0,
            direction=target.direction,
            lw=DEFAULT_LW, dash=None,
            color=self._resolve_color(elem.color),
            label=elem.text,
            extra={
                "align": elem.align,
                "font_size": self._text_font_size(elem.font_size),
                "font_family": self._text_font_family(elem.font_family),
            },
            show_id=False, show_dims=False,
            source_line=elem.source_line,
        )
        self._elements.append(pe)

    def _place_textbreak(self, elem: TextBreakElem) -> None:
        target = self._named_elements.get(elem.element_name)
        if target is None:
            raise ParseError(
                f"Line {elem.source_line}: textbreak: element '{elem.element_name}' not found"
            )
        pe = PlacedElement(
            kind="textbreak", number=None,
            x=target.x, y=target.y,
            length=target.length, width=0.0,
            direction=target.direction,
            lw=DEFAULT_LW if elem.lw is None else elem.lw, dash=None,
            color=self._resolve_color(elem.color),
            label=elem.text,
            extra={
                "align": elem.align,
                "font_size": self._text_font_size(elem.font_size),
                "font_family": self._text_font_family(elem.font_family),
            },
            show_id=False, show_dims=False,
            source_line=elem.source_line,
        )
        self._elements.append(pe)

    def _place_textbox(self, elem: TextBoxElem) -> None:
        x, y = self._place_start(elem.absolute)
        pe = PlacedElement(
            kind="textbox", number=self._next_number(),
            x=x, y=y, length=elem.length, width=elem.width,
            direction=self._cursor.direction,
            lw=_lw(elem.lw), dash=elem.dash, color=self._resolve_color(elem.color),
            label=elem.text or None,
            extra={
                "align": elem.align,
                "wrap": elem.wrap,
                "font_size": self._text_font_size(elem.font_size),
                "font_family": self._text_font_family(elem.font_family),
                "text_rows": [],
            },
            **self._flags(),
            source_line=elem.source_line,
        )
        self._elements.append(pe)
        self._register_name(pe, elem.name)
        self._move_cursor_to_end(x, y, elem.length)

    def _place_textappend(self, elem: TextAppendElem) -> None:
        target = self._named_elements.get(elem.element_name)
        if target is None:
            raise ParseError(
                f"Line {elem.source_line}: textappend: element '{elem.element_name}' not found"
            )
        if "text_rows" not in target.extra:
            target.extra["text_rows"] = []
        target.extra["text_rows"].append({
            "text": elem.text,
            "align": elem.align,
            "font_size": self._text_font_size(elem.font_size),
            "font_family": self._text_font_family(elem.font_family),
            "color": self._resolve_color(elem.color),
        })
