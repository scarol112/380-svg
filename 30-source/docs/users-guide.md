<!-- $Source: /srv/380-svg/30-source/docs/RCS/users-guide.md,v $ $Revision: 1.7 $ $Date: 2026/04/21 15:40:29 $ -->
# Floor Plan Generator — User's Guide

## Running the program

### Shell driver (recommended)

```
bin/380-010.sh <input.dsl> [output.svg]
```

- `input.dsl` — required; path to your drawing description file
- `output.svg` — optional; defaults to `output.svg` in the current directory

### Python directly

```
uv run python -m floorplan.cli <input.dsl> [-o output.svg]
```

Or read from stdin:

```
cat myplan.dsl | uv run python -m floorplan.cli -o output.svg
```

### Viewing the output

Open `assets/380-030.html` in a browser. It displays the SVG and refreshes
automatically every 6 seconds. Use the path field in the toolbar to point it
at your output file if it is not at the default `../output.svg`.

---

## Input file format

One element or directive per line. Everything after `#` on a line is a comment
and is ignored. Blank lines are ignored.

```
# This is a comment
direction 90
rect 12 10 "Living Room"
```

### Measurements

Dimensions are in **feet** unless a unit suffix is given.

| Written | Meaning |
|---|---|
| `12` | 12 feet |
| `12.5` | 12.5 feet |
| `12'` | 12 feet |
| `6"` | 6 inches (0.5 ft) |
| `12'6"` | 12 feet 6 inches |
| `2px` | 2 SVG pixels — **line weight only** |
| `0px` | Invisible — element occupies space and advances the cursor, but nothing is drawn and no annotations are shown |

### Drawing cursor

Elements are placed one after another starting from the **canvas origin** (the
top-left of the first element). Each element advances the cursor by its length
in the current drawing direction. The cursor position becomes the start point
of the next element.

### Drawing direction

```
direction <degrees>
```

Sets the compass direction for subsequent elements.

| Value | Meaning |
|---|---|
| `0` | Up |
| `90` | Right (default) |
| `180` | Down |
| `270` | Left |

`direction` can appear anywhere in the file and takes effect immediately.

### Include

```
include <filename>
include "filename with spaces.dsl"
```

Inserts the contents of another DSL file at the current position. All drawing
state (cursor position, direction, elementid/dimensions flags) carries through
as if the included lines were written inline.

- Relative paths resolve from the directory of the including file
- Absolute paths are used as-is
- Circular includes (file A includes file B which includes file A) are an error

```
# plan.dsl
include walls.dsl
include fixtures.dsl
```

### Display directives

```
elementid on|off
dimensions on|off
```

Toggle element reference numbers and dimension labels independently. Both are
`on` by default. The directive takes effect for all elements that follow it;
elements placed before the directive are unaffected.

### Color

```
color <value>
```

Sets the stroke color for all subsequent elements. Default is `black`.

- Named colors: `color red`, `color blue`, `color green`, …
- Hex colors (must be quoted): `color "#ff0000"`
- RGB (must be quoted): `color "rgb(0,128,0)"`
- Reset to default: `color black`

Color applies to strokes only. Wall fill is always dark grey regardless of color.

```
color red
rect 10 8 "Bedroom"
color blue
door 3 right A=2,8
color black
```

To change the color of a single element without affecting subsequent elements, use `C=<value>` on that element:

```
rect 10 8 C=red "Bedroom"
door 3 right C="#aa00aa" A=2,8
line 12 C=blue dashed
```

`C=` uses the same color values as the `color` directive. It overrides the current directive color for that one element only.

### Absolute placement

Any element can be placed at a fixed position by appending `A=<h>,<v>`, where
`h` and `v` are feet from the canvas origin to the element's top-left corner.
The cursor advances to the element's end point after placement, so the next
element continues from there (same as non-absolute placement).

```
door 3 right A=2,10      # place door at (2ft, 10ft) from origin
```

---

## Element types

### `line`

A straight line segment in the current direction.

```
line <length> [<lw>px] [<dash>] [C=<color>] [A=<h>,<v>]
```

```
line 12
line 8'6" 2px
```

---

### `rect`

An open (unfilled) rectangle. `length` is in the drawing direction; `width` is
perpendicular to it.

```
rect <length> <width> [<lw>px] [<dash>] [C=<color>] ["label"] [A=<h>,<v>]
```

```
rect 12 10
rect 10'6" 8' "Bedroom"
rect 14 11 2px "Master Bedroom" A=12,0
```

The label is centered inside the rectangle.

---

### `wall`

A filled (solid) rectangle representing a structural wall. Default thickness
is 6 inches.

```
wall <length> [<thickness>] [<lw>px] [<dash>] [C=<color>] [A=<h>,<v>]
```

```
wall 12                  # 12ft long, 6" thick
wall 12 8"               # 12ft long, 8" thick
```

---

### `door`

A door symbol: a solid line for the door slab and a dashed quarter-circle arc
showing the swing path. The hinge is at the element's start point.

```
door <width> [left|right|in|out] [<lw>px] [<dash>] [C=<color>] [A=<h>,<v>]
```

- `width` — clear opening width
- swing direction — `right` (default), `left`, `in`, or `out` relative to the
  current drawing direction

```
door 3
door 2'8" left
door 3 right A=2,10
```

---

### `window`

Two parallel lines across a wall opening.

```
window <width> [<depth>] [<lw>px] [<dash>] [C=<color>] [A=<h>,<v>]
```

- `width` — opening width
- `depth` — wall thickness (default 6 inches)

The dimension annotation shows the opening width only; wall depth is not
included in the label.

```
window 4
window 3 8"
window 4 A=22,3
```

---

### `arc`

A general-purpose arc, drawn clockwise from the element's start point.

```
arc <radius> <sweep-degrees> [<lw>px] [<dash>] [C=<color>] [A=<h>,<v>]
```

```
arc 3 90           # quarter circle, 3ft radius
arc 5 180          # semicircle, 5ft radius
```

---

### `arrow`

A line with an arrowhead at the end.

```
arrow <length> [<lw>px] [<dash>] [C=<color>] [A=<h>,<v>]
```

```
arrow 6
arrow 4 A=0,15
```

---

### `label`

A text annotation. Does not advance the cursor. Labels always render
horizontally regardless of the current drawing direction.

```
label "text" [left|center|right] [<size>] [A=<h>,<v>]
```

- alignment — `left` (default), `center`, or `right`
- `<size>` — font size in SVG pixels (default 10)

```
label "North" center A=10,0
label "see detail A" left A=5,20
label "SCALE 1:48" center 14 A=5,25
```

---

## Common options (all elements)

| Option | Description |
|---|---|
| `<n>px` | Line weight in SVG pixels. Default is 1px. |
| `dashed` | Long dashes (8,4) |
| `shortdash` | Short dashes (4,4) |
| `dotted` | Dots (2,2) |
| `center` | Center line — long dash, short dash (12,3,2,3) |
| `hidden` | Hidden line — short dashes (4,2) |
| `C=<color>` | Per-element stroke color override. Named (`C=red`) or quoted CSS (`C="#ff0000"`). Does not affect subsequent elements. |
| `A=<h>,<v>` | Place at absolute position (h,v) in feet from canvas origin. The cursor advances to the element's end point, so the next element continues from there. |

Dash styles apply to all geometry elements (line, rect, wall, door, window, arc, arrow).

```
line 12 dashed
rect 10 8 hidden "Future Addition"
wall 6 dotted
```

---

## Output

The SVG is letter-size landscape (11 × 8.5 in). The drawing is automatically
scaled to fill an 8 × 10 inch print rectangle and centered on the page.

Each geometry element (line, rect, wall, door, window, arc, arrow) is assigned
a reference number rendered in **red** near its start point. Dimension labels
showing actual measurements appear alongside each element in a slightly larger
font. The renderer automatically nudges annotations to avoid overlapping each
other. Both can be toggled with the `elementid` and `dimensions` directives.

---

## Example

```
# Two-room layout with a shared wall, door, and window

direction 90

rect 12 10 "Living Room"
rect 10 10 "Bedroom"

# Door in the bottom wall of the living room
door 3 right A=2,10

# Window on the right wall of the bedroom
window 4 A=22,3
```

Run:

```
bin/380-010.sh myplan.dsl myplan.svg
```
