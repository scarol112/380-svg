<!-- $Source: /srv/380-svg/30-source/docs/RCS/users-guide.md,v $ $Revision: 1.17 $ $Date: 2026/05/02 11:15:05 $ -->
# Floor Plan Generator — User's Guide

### Running the program

#### Shell driver (recommended)

```
bin/380-010.sh <input.dsl> [output.svg]
```

- `input.dsl` — required; path to your drawing description file
- `output.svg` — optional; defaults to `output.svg` in the current directory

#### Python directly

```
uv run python -m floorplan.cli <input.dsl> [-o output.svg]
```

Or read from stdin:

```
cat myplan.dsl | uv run python -m floorplan.cli -o output.svg
```

#### Viewing the output

Open `assets/380-030.html` in a browser. It displays the SVG and refreshes
automatically every 6 seconds. Use the path field in the toolbar to point it
at your output file if it is not at the default `../output.svg`.

---

### Input file format

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

#### Aliases

Every keyword has a short alias so common sequences stay compact. Aliases are
case-insensitive and can be mixed freely with full names.

| Full name | Alias | Full name | Alias |
|---|---|---|---|
| `line` | `l` | `direction` | `dir` |
| `rect` | `r` | `elementid` | `eid` |
| `wall` | `w` | `dimensions` | `dim` |
| `door` | `d` | `color` | `col` |
| `window` | `wi` | `include` | `inc` |
| `arc` | `a` | `showcornerxy` | `sxy` |
| `arrow` | `aw` | `moveto` | `mto` |
| `point` | `p` | `lineto` | `lto` |
| `label` | `lb` | `textstyle` | `tstyle` |
| `textline` | `txl` | `textbreak` | `txbr` |
| `textbox` | `tbox` | `textappend` | `tapp` |

```
dir 90; l 10; dir 0; l 8; dir 270; l 10; dir 180; l 8
eid off; dim off
p C=red A=3,3; p C=blue A=5,5
```

#### Measurements

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

#### Drawing cursor

Elements are placed one after another starting from the **canvas origin** (the
top-left of the first element). Each element advances the cursor by its length
in the current drawing direction. The cursor position becomes the start point
of the next element.

#### Drawing direction

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

#### Include

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

#### Variables

Numeric variables let you name dimensions and positions for reuse and calculation.

**Assign** with a bare `name = expression`:

```
roomw = 14
roomh = 11
lw    = 2
half  = $roomw * 0.5
inner = $roomw - 2
```

Arithmetic operators `+ - * /` with standard precedence are supported. References to other variables use `$name`.

**Inline expressions**: anywhere a number appears, `(expr)` is evaluated immediately. Bare variable names inside `(...)` are variable references — no `$` prefix needed inside the parens. Nested parentheses work.

```
n = 8
line (n/2)                    # length 4
rect (roomw - 2) $roomh       # subtract from a variable
door 3 A=2,(roomh - 0.5)      # expression in A= coordinate
x = (a * (b + c))             # nested parens in assignment
```

Parentheses inside double-quoted label strings are **not** evaluated — they are literal text.

---

Compound assignment adjusts an already-defined variable:

```
margin = 1
roomw = 14
roomw -= 1    # trim: roomw is now 13
roomw += 0.5  # roomw is now 13.5
```

**Reference** a variable anywhere a number appears:

```
rect $roomw $roomh "Main Room"
wall $roomh 2px A=$roomw,0
line 10 ${lw}px dashed
label "${roomw}x${roomh} room" center A=0,0
```

Two reference forms, identical behavior:

| Form | Use | Example |
|---|---|---|
| `$name` | Standalone (whitespace-separated) | `rect $roomw $roomh` |
| `${name}` | Embedded into a token | `${lw}px`, `"${w}x${h} ft"` |

**System variables** — names starting with `__` (double underscore) are reserved and read-only. Attempting to assign to any `__`-prefixed name is an error.

| Variable | Alias | Value |
|---|---|---|
| `$__cursorx` | `$__cx` | Cursor x in feet from canvas origin (same coordinate space as `A=`) |
| `$__cursory` | `$__cy` | Cursor y in feet from canvas origin |
| `$__dir` | — | Current drawing direction in degrees (0=up, 90=right, 180=down, 270=left) |
| `$__mltodir` | — | Compass bearing of the most recent `moveto` or `lineto`, in degrees |

All system variables update after every statement.

```
dir 90
rect 12 10 "Living Room"
point C=red A=$__cx,$__cy       # red dot at cursor after rect
dir 0
line (__dir / 90)               # length = 0/90 = 0 (placeholder; __dir=0 after dir 0)
lb "__dir=${__dir}" A=0,1       # label showing current direction
```

Variables are shared across `include` files.

---

#### Display directives

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

##### `showcornerxy`

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

#### Color

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

#### Absolute placement

Any element can be placed at a fixed position by appending `A=<h>,<v>`, where
`h` and `v` are feet from the canvas origin to the element's top-left corner.
The cursor advances to the element's end point after placement, so the next
element continues from there (same as non-absolute placement).

```
door 3 right A=2,10      # place door at (2ft, 10ft) from origin
```

---

### Element types

#### `line`

A straight line segment in the current direction.

```
line <length> [<lw>px] [<dash>] [C=<color>] [A=<h>,<v>]
```

```
line 12
line 8'6" 2px
```

---

#### `rect`

An open (unfilled) rectangle. `length` is in the drawing direction; `width` is
perpendicular to it.

```
rect <length> <width> [<lw>px] [<dash>] [C=<color>] ["label"] [A=<h>,<v>] [@name]
```

```
rect 12 10
rect 10'6" 8' "Bedroom"
rect 14 11 2px "Master Bedroom" A=12,0
rect 4 0.8 @panel "**Schedule**" C="lightgray"
```

The label is centered inside the rectangle. Inline markup (`*italic*`, `**bold**`) is supported in the label. A named rect can receive `textappend` rows that expand it downward.

---

#### `wall`

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

#### `door`

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

#### `window`

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

#### `arc`

A general-purpose arc, drawn clockwise from the element's start point.

```
arc <radius> <sweep-degrees> [<lw>px] [<dash>] [C=<color>] [A=<h>,<v>]
```

```
arc 3 90           # quarter circle, 3ft radius
arc 5 180          # semicircle, 5ft radius
```

---

#### `arrow`

A line with an arrowhead at the end.

```
arrow <length> [<lw>px] [<dash>] [C=<color>] [A=<h>,<v>]
```

```
arrow 6
arrow 4 A=0,15
```

---

#### `moveto`

Moves the cursor to an absolute canvas position without drawing anything. No element ID or dimension annotation is produced.

```
moveto <x> <y> [A=<sx>,<sy>]
```

- `x`, `y` — destination in feet from the canvas origin
- `A=<sx>,<sy>` — start point override for `__mltodir` calculation only; the cursor still moves to `(x, y)`

Updates `$__mltodir` to the compass bearing from start to destination. Does not change `$__dir`.

```
moveto 5 0          # jump cursor to (5, 0)
mto 0 0 A=5,0       # __mltodir = 270° (leftward); cursor moves to (0, 0)
```

---

#### `lineto`

Draws a straight line from the current cursor (or from `A=sx,sy`) to the specified destination, then advances the cursor there. The element is numbered and dimensioned like any other geometry element.

```
lineto <x> <y> [<lw>px] [<dash>] [C=<color>] [A=<sx>,<sy>]
```

- `x`, `y` — destination in feet from the canvas origin
- `A=<sx>,<sy>` — overrides the start point (same semantics as on other elements)
- All standard line options apply: line weight, dash style, per-element color

Updates `$__mltodir` to the compass bearing of the drawn line. Does not change `$__dir`.

```
lineto 10 5                     # diagonal from cursor to (10, 5)
lto 14 8 2px dashed C=blue A=10,0  # blue dashed line from (10, 0) to (14, 8)
lb "bearing: ${__mltodir}"      # show the last lineto direction
```

---

#### `point`

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

#### `label`

A text annotation. Does not advance the cursor. Labels always render
horizontally regardless of the current drawing direction.

```
label "text" [left|center|right] [<size>] [font=<family>] [A=<h>,<v>] [@name]
```

- alignment — `left` (default), `center`, or `right`
- `<size>` — font size in SVG pixels (default 10, or the current `textstyle` size)
- `font=<family>` — font family for this label only (e.g. `font=serif`)
- `@name` — register this label under a name for later reference

Quoted text supports **inline markup** and **line breaks** — see [Text styling](#text-styling) below.

```
label "North" center A=10,0
label "see detail A" left A=5,20
label "SCALE 1:48" center 14 A=5,25
lb "**Bold title**\nSubtitle" center 12 A=0,0
```

---

### Text styling

#### Element naming

Any element can be tagged with `@name` at the end of its statement. The name is used to anchor text elements to that element later.

```
line 12 @corridor
rect 14 10 @living_room "Bedroom"
wall 8 0.5 @north_wall
```

Names are case-sensitive identifiers. A later `@name` on a different element replaces the earlier registration.

---

#### Inline bold, italic, and line breaks

Inside any double-quoted string you can use **Markdown-style** span markers:

| What you write | What renders |
|---|---|
| `*text*` | *italic* |
| `**text**` | **bold** |
| `***text***` | ***bold italic*** |
| `\*` | literal asterisk `*` |
| `\n` | line break |

```
lb "Normal *italic* and **bold** text"
lb "***Critical notice***" center 12
lb "Price: $4.50/sq\*ft"
lb "Room: Bedroom\nArea: 168 sq ft\nFinish: Hardwood"
```

`\n` creates a new line. A double `\n\n` leaves a blank line gap. These work in `label`, `textbox`, `textappend`, `textline`, and `textbreak`.

Unclosed markup (e.g. `*only one asterisk`) is treated as literal text.

---

#### `textstyle` — default font

Sets the default font size and family for all subsequent text elements. Works like `color` does for strokes.

```
textstyle [<size>] [font=<family>] [normal]
```

- `<size>` — default font size in SVG pixels
- `font=<family>` — CSS font family: `sans-serif`, `serif`, `monospace`, or any CSS font name
- `normal` — resets both to defaults (10px, sans-serif)

Any text element can override locally with its own `<size>` or `font=<family>`.

```
textstyle 12 font=serif        # 12px serif for everything that follows
textstyle font=monospace       # change family only
textstyle normal               # back to 10px sans-serif
lb "Title" 18                  # local override: 18px, current family
lb "Body" font=sans-serif      # local font override only
```

---

#### `textline` — text alongside a named element

Places text alongside a named line or other element, rotated to match its direction. Does not advance the cursor.

```
textline "text" <name> [left|center|right] [<size>] [font=<family>] [C=<color>]
```

- `<name>` — a previously registered element name (via `@name`)
- alignment — where on the element to anchor the text: `left` = at the start, `center` = centred (default), `right` = at the end
- Text is offset slightly away from the element and rotated to stay readable

```
dir 90
l 14 @corridor
textline "Corridor" corridor center 10
txl "**North Wall**" north_wall left 12 C=blue
```

---

#### `textbreak` — text that visually breaks a line

Places a labelled border box on a named line. A white-filled rectangle masks the line behind the text; a thin stroked border box is drawn around the text. The line's geometry is unchanged — SVG layer order makes the box appear in front. Does not advance the cursor.

```
textbreak "text" <name> [left|center|right] [<size>] [font=<family>] [C=<color>]
```

```
l 14 @front_wall
textbreak "Front Wall" front_wall center 10
txbr "**Section A-A**" section_line center 12
```

---

#### `textbox` — text inside a drawn rectangle

A stroked rectangle with text inside. Behaves like `rect` for cursor advancement — the cursor moves forward by `length` in the current direction.

```
textbox <length> <width> ["text"] [left|center|right] [wrap] [<size>] [font=<family>]
        [<lw>px] [<dash>] [C=<color>] [A=<h>,<v>] [@name]
```

- `wrap` — word-wraps the text to fit within the box width using `<tspan>` elements
- `@name` — name the box so `textappend` can add rows to it later

Text supports inline markup and `\n` line breaks. With `wrap`, explicit `\n` paragraph breaks are honoured before word-wrapping is applied.

```
tbox 6 2 "Long note that wraps inside the box" left wrap 9
tbox 8 1.5 "**Title**" center 14 2px A=0,12
tbox 4 0.8 @panel "**Schedule**" C="lightgray"
```

A `textbox` with `width=0` starts at zero height and grows downward via `textappend`.

---

#### `textappend` — add rows to a named rect or textbox

Appends a text row below the current content of a named `rect` or `textbox`, expanding the element's border downward. Does not advance the cursor.

```
textappend "text" <name> [left|center|right] [<size>] [font=<family>] [C=<color>]
```

- Each call adds one row (or more, if `\n` appears in the text)
- An empty string `""` inserts a blank spacer row

```
rect 4 0.8 @panel "**Schedule**" C="lightgray"
textappend "Area: 168 sq ft" panel
textappend "*Finish:* Hardwood" panel
textappend "" panel             # blank spacer
textappend "Updated: 2026-05" panel right 8

tbox 4 0.6 @notes "**Notes**"
tapp "Item 1\nItem 2" notes    # two rows from one call
tapp "" notes                  # blank line
tapp "Item 3" notes
```

---

### Common options (all elements)

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
| `@name` | Register this element under a name for later reference by `textline`, `textbreak`, or `textappend`. |
| `font=<family>` | *(text elements and `label` only)* Per-element font family override. |

Dash styles apply to all geometry elements (line, rect, wall, door, window, arc, arrow).

```
line 12 dashed
rect 10 8 hidden "Future Addition"
wall 6 dotted
```

---

### Output

The SVG is letter-size landscape (11 × 8.5 in). The drawing is automatically
scaled to fill an 8 × 10 inch print rectangle and centered on the page.

Each geometry element (line, rect, wall, door, window, arc, arrow) is assigned
a reference number rendered in **red** near its start point. Dimension labels
showing actual measurements appear alongside each element in a slightly larger
font. The renderer automatically nudges annotations to avoid overlapping each
other. Both can be toggled with the `elementid` and `dimensions` directives.

---

### Example

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
