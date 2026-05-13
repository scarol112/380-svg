# Issue #20 — Numeric Variables: Design Plan

## Overview

Add numeric variables to the DSL so that dimensions and positions can be named,
reused, and computed. Also add built-in read-only variables `cursorx` and
`cursory` that update after every placed element.

---

## Syntax

### Assignment

```
roomw = 12
roomh = 8.5
lw = 2
offset = roomw * 0.5
half = roomw * 0.5 + 1
```

- Bare `name = expression` — no keyword required
- Arithmetic `+ - * /` with standard operator precedence
- Right-hand side may reference previously assigned variables (via `$name`)

### Reference

Two forms, identical semantics:

| Form | Use | Example |
|---|---|---|
| `$name` | Standalone (whitespace-separated) | `rect $roomw $roomh` |
| `${name}` | Embedded (concatenates with adjacent chars) | `line 10 ${lw}px`, `"${roomw}x${roomh} ft"` |

```
rect $roomw $roomh "${roomw}x${roomh} ft room"
door 3 ${lw}px A=$offset,$roomh
line 10 ${lw}px dashed
point A=$cursorx,$cursory
```

### Built-in variables

| Name | Value | Read-only |
|---|---|---|
| `$cursorx` | Cursor x position (feet from canvas origin) after last element | Yes |
| `$cursory` | Cursor y position (feet from canvas origin) after last element | Yes |

`cursorx` and `cursory` match the A= coordinate space. Assigning to them is an
error.

### Scope

Variables are shared across `include` files — one variable table for the
entire drawing. A variable set in the parent file is visible in included files
and vice versa.

---

## Variable names

`[A-Za-z_][A-Za-z0-9_]*` — same character set as identifier names in most
languages. Reserved: `cursorx`, `cursory`.

---

## Architecture

### Problem

`cursorx`/`cursory` are runtime values updated as elements are placed. The
current pipeline parses all statements first, then places them, so cursor
position is not available at parse time.

### Solution: interleaved execution

A new `interpreter.py` module replaces the `parse_file() + placer.place_all()`
call in `cli.py`. It processes statements one at a time:

```
for each statement:
    if assignment → evaluate expression, store in vars
    if element/directive → substitute $vars → parse → place → update cursor vars
    if include → recurse with same vars and placer
```

Existing `parse_file()` is left unchanged.

### Variable substitution

Text-level: `$varref` and `${varref}` are replaced with their numeric values
before tokenizing. This means:

- `${lw}px` → `2px` → tokenized as a PX token
- `"${roomw}x${roomh} ft"` → `"12x10 ft"` → quoted label string
- `A=$cursorx,$cursory` → `A=10,-8` → ABSOLUTE token

Expression evaluation uses Python's `eval()` restricted to numeric operators
(`+ - * / ( )` and numeric literals only).

---

## Files

| File | Change |
|---|---|
| `src/svgdsl/interpreter.py` | **New** — `execute_dsl()`, variable substitution, expression evaluator, interleaved loop |
| `src/svgdsl/cli.py` | Replace `parse_file + place_all` with `execute_dsl` |
| `src/svgdsl/dsl/parser.py` | No change — `_parse_line` reused as-is from interpreter |
| `docs/design.md` | Update |
| `docs/users-guide.md` | Update |

---

## Examples

```
# Named dimensions
roomw = 14
roomh = 11
wallthk = 8"
doorw = 3

dir 90
rect $roomw $roomh "Master Bedroom"

# Door 2ft in from corner
door $doorw A=2,$roomh

# Wall on right side
wall $roomh $wallthk A=$roomw,0

# Mark cursor position after placing last element
point C=red A=$cursorx,$cursory
```

```
# Arithmetic
outer = 20
margin = 1
inner = outer - margin * 2    # = 18
rect $inner $inner "Inner Room"
```

```
# Variables in labels and px values
lw = 2
rect 10 8 ${lw}px "10 x 8"
line 10 ${lw}px dashed
```
