#!/usr/bin/env bash
# Usage: 380-010.sh <input.dsl> [<output.svg>]
set -euo pipefail
INPUT="${1:-}"
OUTPUT="${2:-output.svg}"

if [[ -z "$INPUT" ]]; then
    echo "Usage: $0 <input.dsl> [<output.svg>]" >&2
    exit 1
fi

INPUT="$(realpath "$INPUT")"
cd "$(dirname "$0")/.."
uv run python -m floorplan.cli "$INPUT" -o "$OUTPUT" "${@:3}"
