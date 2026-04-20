# App working title: svg

## Project tools
uv for dependency management

## Project assets
bin/380-010.sh - shell driver for the main program
assets/380-030.html - frame for displaying the svg in progress
assets/380-031.css - css for 380-030.html
assets/380-032.js - javascript for 380-030.html

## Display
SVG files being developed are displayed by 380-030.html which refreshes every 15 seconds to show recent changes to the underlying file.

## SVG structure
- Default file layout for print is letter-size paper, landscape orientation
- By default the image is centered horizontally and vertically on the page and scaled to fill an 8 by 10 inch print rectangle
- Auto-scale is computed after all elements are parsed: the bounding box of all placed elements is calculated, then a uniform scale factor is derived so the drawing fits within 768×960 SVG units (8×10 inches at 96dpi). Scale = min(768 / total_width_ft, 960 / total_height_ft).
- **Canvas origin** is the top-left of the first user-defined element's bounding box, fixed for the lifetime of the drawing. All absolute ("A=") offsets are measured from this point.
- User-defined elements are numbered for reference. Numbers are displayed in a small font above horizontal elements and to the left of vertical elements. Only geometry elements are numbered (line, rect, wall, door, window, arc) — not labels or directives.
- Digital dimensions are displayed below or to the right of user-defined elements, or with a callout line if they would overlap other elements.
- Labels always render horizontally (readable) regardless of the current drawing direction.

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
- Lines beginning with "#" are comments, to be ignored
- Blank lines are ignored
- Tokens are whitespace-separated

### Directives (non-drawing lines)
```
direction <degrees>    # set drawing direction: 0=up, 90=right, 180=down, 270=left
```
Default direction is 90 (rightward).

### Measurements
- `12` = 12 feet
- `12.5` = 12.5 feet
- `12'6"` = 12 feet 6 inches
- `6"` = 6 inches (= 0.5 feet)
- `2px` = line weight in SVG user units (96dpi screen pixels); for line weight only

### Drawing Coordinate System
Compass degrees map to SVG delta vectors (Y increases downward in SVG):
- 0° (up) → delta (0, −1)
- 90° (right) → delta (+1, 0)
- 180° (down) → delta (0, +1)
- 270° (left) → delta (−1, 0)

All internal geometry is stored in feet (float). The SVG renderer multiplies by `scale_factor` (SVG units/foot) at render time.

### Element syntax (positional)
```
<type> <length> [<width>] [<lw>px] [<begin_h>,<begin_v>] [<end_h>,<end_v>] [A=<h>,<v>] ["label"]
```

Optional tokens after length/width (order-independent within their type):
- `<n>px` — line weight override (SVG user units)
- `<h>,<v>` (first coord pair) — **Begin Point**: (h,v) offset from element top-left where this element connects to the previous element's End Point. Default: center of element's trailing side.
- `<h>,<v>` (second coord pair) — **End Point**: (h,v) offset from element top-left where the next element connects. Default: center of element's leading side.
- `A=<h>,<v>` — absolute placement: (h,v) from canvas origin to this element's top-left. Does **not** move the drawing cursor.
- `"text"` — inline annotation string

### Element Types

```
line <length> [<lw>px]
rect <length> <width> [<lw>px] ["label"]
wall <length> [<thickness>]          # default thickness = 6"
door <width> [left|right|in|out]     # default swing = right
window <width> [<depth>]             # default depth = 6"
arc <radius> <sweep-degrees> [<lw>px]
arrow <length> [<lw>px]
label "text" [left|center|right]     # default align = left
```

### Drawing Sequence
Beginning at the canvas origin, elements are drawn one after the other in the current drawing direction, with the Begin Point of the new element adjacent to the End Point of the previous element. An element with `A=` is placed absolutely and does not advance the cursor.

### Element Placement
- `A=<h>,<v>` is the horizontal and vertical distance from the canvas origin to the top-left corner of the element.
- If no offset is specified, the new element begins where the previous one ended.
- Absolute placement (`A=`) does not move the drawing cursor.

### Example DSL file
```
# Simple 12×10 ft bedroom
direction 90
rect 12 10 "Bedroom"
door 3 right A=2,10
window 4 A=12,3
```
