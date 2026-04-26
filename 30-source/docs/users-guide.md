<!-- $Source: /srv/380-svg/30-source/docs/RCS/users-guide.md,v $ $Revision: 1.10 $ $Date: 2026/04/26 15:03:31 $ -->
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

One element or directive per line. Multiple statements can be placed on the
same line by separating them with semicolons (`;`). Everything after `#` on a
line is a comment and is ignored. Blank lines are ignored.

```
# This is a comment
direction 90
rect 12 10 "Living Room"

# Semicolons allow compact notation
direction 90; line 10; direction 0; line 8
elementid off; dimensions off
point C=red A=2,3; point C=blue A=5,6
```

Semicolons inside double-quoted strings are treated as literal characters, not
separators:

```
label "hello; world"   # label text is  hello; world
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
showcornerxy on|off
```

Toggle element reference numbers, dimension labels, and corner coordinate
markers independently. `elementid` and `dimensions` are `on` by default;
`showcornerxy` is `off` by default. Each directive takes effect immediately
and applies to elements that follow it; elements placed before the directive
are unaffected.

#### `showcornerxy`

When `on`, a coordinate marker is added at each point where the drawing
direction changes. The marker shows the cursor position in decimal feet at
the moment of the turn.

Each marker consists of a short grey leader line drawn at 45° from the corner
point (with a small gap at each end so it does not touch the point or the
text), followed by the coordinates — for example `10.5, -8`.

The leader direction is automatically chosen from NE, NW, SE, or SW to avoid
overlapping other drawn elements and labels. When `showcornerxy` is active,
the drawing is scaled down as needed so all markers fit within the page margins.

```
showcornerxy on
direction 90
line 10             # cursor moves to (10, 0)
direction 0         # corner marker appears at (10, 0) labelled "10, 0"
line 8              # cursor moves to (10, -8)
direction 270       # corner marker appears at (10, -8) labelled "10, -8"
showcornerxy off
direction 180       # no marker — showcornerxy is off
```

`showcornerxy` is useful during drawing development to verify that walls meet
at the correct coordinates.

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

### `point`

A filled circle 3 px in diameter, drawn at the current cursor position or at
an absolute position. Useful for marking reference points, corners, or
measurement targets.

```
point [<lw>px] [C=<color>] [A=<h>,<v>]
```

- `<lw>px` — stroke width (default 1 px); use `0px` to suppress rendering
- `C=<color>` — fill and stroke color (default: current `color` directive)
- `A=<h>,<v>` — place at an absolute position instead of the cursor

**Cursor**: `point` does **not** advance the cursor. The drawing position after
a `point` is the same as before it, so subsequent elements continue from the
same location.

**Annotations**: dimension labels are never shown for points. Element ID
numbers are shown when `elementid` is on. When `showcornerxy` is on, a
coordinate annotation in the corner-marker style is placed at the point.

```
point                      # mark the current cursor position
point C=red                # red dot at the current position
point A=10,5               # dot at (10ft, 5ft) from canvas origin; cursor unchanged
point 0px                  # invisible — occupies no space, produces no output
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
