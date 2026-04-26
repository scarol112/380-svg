import argparse
import sys
from pathlib import Path

from .dsl.parser import parse_file, ParseError
from .layout.placer import ElementPlacer
from .layout.scaler import compute_scale
from .render.svg import render_svg

_DARKORANGE = "\033[38;5;208m"
_RESET      = "\033[0m"


def _err(msg: str) -> None:
    """Print an error message in darkorange to stderr."""
    tty = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
    if tty:
        print(f"{_DARKORANGE}{msg}{_RESET}", file=sys.stderr)
    else:
        print(msg, file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="floorplan",
        description="Generate SVG floor plans from a DSL description file.",
    )
    ap.add_argument("input", nargs="?", help="DSL input file (default: stdin)")
    ap.add_argument("-o", "--output", default="output.svg", help="SVG output file (default: output.svg)")
    args = ap.parse_args()

    if args.input:
        source_path = Path(args.input)
        try:
            text = source_path.read_text()
        except FileNotFoundError:
            _err(f"Error: input file not found: {source_path}")
            sys.exit(1)
    else:
        source_path = None
        text = sys.stdin.read()

    try:
        nodes = parse_file(text, source_path=source_path)
    except ParseError as e:
        _err(f"Error: {e}")
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
