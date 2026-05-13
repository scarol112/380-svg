import argparse
import sys
from pathlib import Path

from .dsl.parser import ParseError
from .interpreter import execute_dsl
from .layout.scaler import compute_scale
from .render.svg import render_svg

_DARKORANGE = "\033[38;5;208m"
_RESET      = "\033[0m"

_PAPER_SIZES: dict[str, tuple[int, int]] = {
    "letter":  (1056, 816),   # 11 × 8.5 in landscape @ 96 dpi
    "tabloid": (1632, 1056),  # 17 × 11 in landscape @ 96 dpi
}


def _err(msg: str) -> None:
    """Print an error message in darkorange to stderr."""
    tty = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
    if tty:
        print(f"{_DARKORANGE}{msg}{_RESET}", file=sys.stderr)
    else:
        print(msg, file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="svgdsl",
        description="Generate SVG floor plans from a DSL description file.",
    )
    ap.add_argument("input", nargs="?", help="DSL input file (default: stdin)")
    ap.add_argument("-o", "--output", default="output.svg", help="SVG output file (default: output.svg)")
    ap.add_argument("-p", "--paper", default="letter", choices=_PAPER_SIZES,
                    help="Paper size: letter (11×8.5in, default) or tabloid (17×11in)")
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
        elements = execute_dsl(text, source_path=source_path)
    except ParseError as e:
        _err(f"Error: {e}")
        sys.exit(1)

    if not elements:
        print("Warning: no elements found in input.", file=sys.stderr)

    page_w, page_h = _PAPER_SIZES[args.paper]
    scale, tx, ty = compute_scale(elements, page_w=page_w, page_h=page_h)
    svg = render_svg(elements, scale, tx, ty, page_w=page_w, page_h=page_h)

    Path(args.output).write_text(svg)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
