# Floor Plan SVG Generation
Domain-specific languages for architectural drawings

## Initial research with Claude

Several DSLs exist:

- **OpenSCAD** — code-based 3D/2D modeling, but more for mechanical parts than floor plans
- **Sweet Home 3D** has its own XML format
- **IFC (Industry Foundation Classes)** — the professional standard for building information modeling, but very verbose/complex
- **ASCII-art based tools** like `floorplan` that compile to SVG

### Recommended approach

SVG is the practical choice for generating floor plans from a description:
- Floor plans are essentially rectangles, lines, arcs (door swings), and text labels
- SVG handles all of these cleanly
- Renders in any browser with no tooling required
- Claude can generate SVG directly from a room-by-room description

### To proceed

Describe the layout — rooms, approximate dimensions, which walls are shared,
door/window placements — and Claude can produce an SVG directly.
