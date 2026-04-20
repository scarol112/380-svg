DASH_PATTERNS: dict[str, str] = {
    "dashed":    "8,4",
    "shortdash": "4,4",
    "dotted":    "2,2",
    "center":    "12,3,2,3",
    "hidden":    "4,2",
}


def dash_attr(dash: str | None) -> str:
    """Return a stroke-dasharray attribute string, or empty string if solid."""
    if dash and dash in DASH_PATTERNS:
        return f' stroke-dasharray="{DASH_PATTERNS[dash]}"'
    return ""
