import argparse
import sys
from pathlib import Path

from .dsl.parser import parse_file, ParseError
from .layout.placer import ElementPlacer
from .layout.scaler import compute_scale
from .render.svg import render_svg


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="floorplan",
        description="Generate SVG floor plans from a DSL description file.",
    )
    ap.add_argument("input", nargs="?", help="DSL input file (default: stdin)")
    ap.add_argument("-o", "--output", default="output.svg", help="SVG output file (default: output.svg)")
    args = ap.parse_args()

    if args.input:
        text = Path(args.input).read_text()
    else:
        text = sys.stdin.read()

    try:
        nodes = parse_file(text)
    except ParseError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if not nodes:
        print("Warning: no elements found in input.", file=sys.stderr)

    placer = ElementPlacer()
    elements = placer.place_all(nodes)

    scale, tx, ty = compute_scale(elements)
    svg = render_svg(elements, scale, tx, ty)

    Path(args.output).write_text(svg)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
