<!-- $Source: /srv/380-svg/30-source/docs/RCS/design.md,v $ $Revision: 1.16 $ $Date: 2026/04/29 22:24:20 $ -->
# App working title: svg

## Project tools
uv for dependency management

## Project assets
bin/380-010.sh - shell driver for the main program
assets/380-030.html - frame for displaying the svg in progress
assets/380-031.css - css for 380-030.html
assets/380-032.js - javascript for 380-030.html

## Display
SVG files being developed are displayed by 380-030.html which refreshes every 6 seconds to show recent changes to the underlying file.

## SVG structure
- Default file layout for print is letter-size paper, landscape orientation
- By default the image is centered horizontally and vertically on the page and scaled to fill an 8 by 10 inch print rectangle
- Auto-scale is computed after all elements are parsed: the bounding box of all placed elements is calculated, then a uniform scale factor is derived so the drawing fits within 768×960 SVG units (8×10 inches at 96dpi). Scale = min(768 / total_width_ft, 960 / total_height_ft).
- **Canvas origin** is the top-left of the first user-defined element's bounding box, fixed for the lifetime of the drawing. All absolute ("A=") offsets are measured from this point.
- User-defined elements are numbered for reference. Numbers are displayed in **red** in a small font above horizontal elements and to the left of vertical elements. Only geometry elements are numbered (line, rect, wall, door, window, arc) — not labels or directives. Element ID display can be toggled with `elementid on/off`.
- Digital dimensions are displayed below or to the right of user-defined elements. The renderer automatically detects and resolves text overlaps by nudging annotations further from the element. Dimension display can be toggled with `dimensions on/off`. For `window` elements the annotation shows the opening width only (not wall depth).
- Invisible elements (`0px` line weight) receive no annotations.
- Labels always render horizontally (readable) regardless of the current drawing direction.
- **`point` cursor behaviour**: unlike all other geometry elements, `point` does not advance the cursor. The dot marks the current position (or an `A=` position) without affecting subsequent element placement. Dimension labels are never shown for points; element ID numbers are shown when `elementid` is on. When `showcornerxy` is on, a coordinate annotation in the corner-marker style is emitted at the point's position.
- **Corner coordinate markers** (`showcornerxy on`): at each `direction` change (only when the angle actually changes), a small annotation is emitted at the cursor's current position showing the corner's coordinates in decimal feet. Each marker is a short leader line (5 px gap from the point, 14 px line, 3 px gap to text) rendered in grey. The leader direction is chosen from NE/NW/SE/SW (preferred NE) to avoid overlapping registered geometry, dimension labels, and `label` elements. The bounding-box scaler iterates to account for the pixel extents of all corner annotations so none are clipped at the page margins.

## SVG XML structure
```xml
<svg width="11in" height="8.5in" viewBox="0 0 1056 816">
  <defs><!-- door arc, window, arrowhead marker symbols --></defs>
  <g id="drawing" transform="translate(tx,ty) scale(k)">
    <!-- all geometry in feet-space, scaled by transform -->
  </g>
</svg>
```

## User description of image elements

### Syntax
- Elements are expressed in files, one element per line
- Multiple statements may appear on one line, separated by semicolons (`;`)
- Lines beginning with "#" are comments, to be ignored
- Trailing `#` comments are stripped before parsing; semicolons inside double-quoted strings are not treated as separators
- Blank lines are ignored
- Tokens are whitespace-separated
- All element and directive keywords have short aliases (see Aliases table)

### Variables

Numeric variables can be assigned and used anywhere a number appears.

**Assignment** — bare `name = expr`, no keyword required:
```
roomw = 12
roomh = 8.5
lw = 2
half = $roomw * 0.5
```

Compound assignment operators `+=` and `-=` adjust an already-defined variable:
```
x = 10
x += 3    # x is now 13
x -= 1    # x is now 12
```

**Reference** — two equivalent forms:
- `$name` — standalone (whitespace-separated)
- `${name}` — embedded (value concatenates with adjacent chars)

```
rect $roomw $roomh "${roomw}x${roomh} ft"
line 10 ${lw}px dashed
door 3 A=$offset,$roomh
point A=$cursorx,$cursory
```

**Built-in read-only variables** (updated after every placed element):

| Name | Value |
|---|---|
| `$cursorx` | Cursor x position in feet from canvas origin (same space as `A=`) |
| `$cursory` | Cursor y position in feet from canvas origin |

Assigning to `cursorx` or `cursory` is an error.

**Arithmetic**: `+ - * /` with standard operator precedence are supported in expressions. References to other variables are written with `$`.

**Inline expressions**: `(expr)` outside quoted strings is evaluated immediately and replaced with its numeric value. Bare identifiers inside `(...)` are variable references — no `$` prefix needed inside the parens. Nested parentheses are supported.

```
line (n/2)                # length = n/2
rect (roomw - 2) $roomh   # width expression
door 3 A=2,(roomh-0.5)    # bare names in A= coordinates
x = (a*(b+c))             # nested parens in assignment RHS
lb "width: ${roomw}"      # parens inside "..." are literal, not evaluated
```

**Scope**: variables are shared across `include` files — one table for the entire drawing.

**Implementation**: `interpreter.py` processes statements one at a time (interleaved parse + place), which is what makes `cursorx`/`cursory` viable. The original `parse_file()` pipeline is retained for any callers that don't use variables.

### Directives (non-drawing lines)
```
direction <degrees>      # set drawing direction: 0=up, 90=right, 180=down, 270=left
elementid on|off         # show/hide element reference numbers (default: on)
dimensions on|off        # show/hide dimension labels (default: on)
showcornerxy on|off      # show/hide corner coordinate markers (default: off)
color <value>            # set stroke color for subsequent elements (default: black)
include <filename>       # insert contents of another DSL file at this position
```
Default direction is 90 (rightward). All display directives take effect immediately and apply to elements that follow them.

`color` accepts any CSS color: named colors (`red`, `blue`, `green`, …) or quoted values for hex and rgb notation (`"#ff0000"`, `"rgb(0,128,0)"`). Use `color black` to reset. Color applies to strokes only; wall fill color is always dark grey.

Per-element color: append `C=<value>` to any geometry element to override the current directive color for that one element only. Same value syntax as the `color` directive.

`include` filenames may be quoted or bare. Relative paths are resolved from the directory of the including file. Circular includes are detected and reported as an error.

### Measurements
- `12` = 12 feet
- `12.5` = 12.5 feet
- `12'6"` = 12 feet 6 inches
- `6"` = 6 inches (= 0.5 feet)
- `2px` = line weight in SVG user units (96dpi screen pixels); for line weight only
- `0px` = invisible element (cursor still advances; no geometry or annotations rendered)

### Drawing Coordinate System
Compass degrees map to SVG delta vectors (Y increases downward in SVG):
- 0° (up) → delta (0, −1)
- 90° (right) → delta (+1, 0)
- 180° (down) → delta (0, +1)
- 270° (left) → delta (−1, 0)

All internal geometry is stored in feet (float). The SVG renderer multiplies by `scale_factor` (SVG units/foot) at render time.

### Element syntax (positional)
```
<type> <length> [<width>] [<lw>px] [<dash>] [C=<color>] [<begin_h>,<begin_v>] [<end_h>,<end_v>] [A=<h>,<v>] ["label"]
```

Optional tokens after length/width (order-independent within their type):
- `<n>px` — line weight override (SVG user units)
- `<dash>` — dash style keyword (see Dash styles)
- `C=<color>` — per-element stroke color override; same values as `color` directive
- `<h>,<v>` (first coord pair) — **Begin Point**: (h,v) offset from element top-left where this element connects to the previous element's End Point. Default: center of element's trailing side.
- `<h>,<v>` (second coord pair) — **End Point**: (h,v) offset from element top-left where the next element connects. Default: center of element's leading side.
- `A=<h>,<v>` — absolute placement: (h,v) from canvas origin to this element's top-left. The cursor is updated to the element's end point, so the next element continues from there.
- `"text"` — inline annotation string

### Element Types

```
line <length> [<lw>px] [<dash>] [C=<color>]
rect <length> <width> [<lw>px] [<dash>] [C=<color>] ["label"]
wall <length> [<thickness>] [<lw>px] [<dash>] [C=<color>]   # default thickness = 6"
door <width> [left|right|in|out] [<lw>px] [<dash>] [C=<color>]  # default swing = right
window <width> [<depth>] [<lw>px] [<dash>] [C=<color>]      # default depth = 6"
arc <radius> <sweep-degrees> [<lw>px] [<dash>] [C=<color>]
arrow <length> [<lw>px] [<dash>] [C=<color>]
point [<lw>px] [C=<color>] [A=<h>,<v>]          # 3px filled circle; cursor does not advance
label "text" [left|center|right] [<size>]        # default align=left, size=10px
```

### Aliases

Every keyword has a short alias. Aliases are case-insensitive and can be mixed freely with full names.

| Full name | Alias |
|---|---|
| `line` | `l` |
| `rect` | `r` |
| `wall` | `w` |
| `door` | `d` |
| `window` | `wi` |
| `arc` | `a` |
| `arrow` | `aw` |
| `point` | `p` |
| `label` | `lb` |
| `direction` | `dir` |
| `elementid` | `eid` |
| `dimensions` | `dim` |
| `color` | `col` |
| `include` | `inc` |
| `showcornerxy` | `sxy` |

### Dash styles

`<dash>` is one of: `dashed`, `shortdash`, `dotted`, `center`, `hidden`.
Omitting a dash keyword renders a solid stroke (default).

| Keyword | `stroke-dasharray` | Use |
|---|---|---|
| `dashed` | `8,4` | General dashed line |
| `shortdash` | `4,4` | Short dashes |
| `dotted` | `2,2` | Dotted line |
| `center` | `12,3,2,3` | Center line |
| `hidden` | `4,2` | Hidden / behind-wall line |

### Drawing Sequence
Beginning at the canvas origin, elements are drawn one after the other in the current drawing direction, with the Begin Point of the new element adjacent to the End Point of the previous element. An element with `A=` is placed absolutely; the cursor still advances to its end point.

### Element Placement
- `A=<h>,<v>` is the horizontal and vertical distance from the canvas origin to the top-left corner of the element.
- If no offset is specified, the new element begins where the previous one ended.
- After any element (absolute or not), the cursor advances to that element's end point. The next element continues from there regardless of whether `A=` was used.

### Example DSL file
```
# Simple 12×10 ft bedroom
direction 90
rect 12 10 "Bedroom"
door 3 right A=2,10
window 4 A=12,3
```
