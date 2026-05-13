# Plan: String Data Type with Explicit Type Declarations

## Context

Issue #38 asks for a string data type in the DSL — `"`/`'` delimited literals, length, concat (`+`/`+=`), substring matching/extraction/replacement, and regex. The user also wants **explicit type declarations** added (numeric remains the default so existing `.dsl` files keep working), and the design must **anticipate a future `tuple` type** so we don't paint ourselves into a corner.

Today the symbol table is already `dict[str, float | str]` (interpreter.py:53) and the lexer already emits `QUOTED` tokens (lexer.py:45–50), but there is no way to *assign* a string to a variable: `_ASSIGNMENT_RE` (interpreter.py:27) sends the RHS through `_eval_expr` (interpreter.py:456), which only returns `float`. There are no string operators or built-in functions. The only path strings travel today is as literal arguments to `label`, `textline`, etc.

Goal: let DSL authors write `string title = "Master Bedroom"`, manipulate it with `+`, `+=`, `len`, `substr`, `match`, `replace`, and have the interpreter cleanly distinguish numeric vs. string vs. (future) tuple values — without breaking any existing `.dsl` files.

## Decisions (confirmed by user)

1. **Declaration syntax:** bare type-keyword prefix — `string s = "hello"`. Numeric stays the default; `x = 5` keeps working unchanged. Extends naturally to a future `tuple t = (...)` and an optional `numeric x = 5` symmetric form.
2. **Quote delimiters:** both `"..."` and `'...'`. Cheap to support — the lexer's feet/inches regexes (`_FEET_INCHES`, `_FEET_ONLY`) all require a digit *before* the `'`, so a `'` at a token boundary unambiguously opens a string literal.
3. **Operation syntax:** mixed — `+` and `+=` for concatenation, function-call form for everything else: `len(s)`, `substr(s, start, end)`, `match(s, pattern)`, `replace(s, pattern, new)`.
4. **Type mismatch policy:** hard error at the use site. **No implicit or explicit coercion** — no `str()` / `num()` builtins. Numbers can still be interpolated into labels via `"${x}"` (existing behavior via `_substitute_vars` and `_fmt_float`); they cannot be concatenated with `+`.

## Design

### 1. Type system (in the interpreter, no new AST)

Introduce a sentinel for variable types in the symbol table. Two ways:

- **Option A (chosen):** keep `vars_: dict[str, float | str]` and infer type from `isinstance` at use sites. Declaration syntax sets the type *implicitly* via the assigned value. Cheapest, fewest moving parts. Future tuple type adds `tuple` to the union.
- Option B: add a parallel `var_types: dict[str, str]` map. More machinery; only needed if we want to reject `string s = 5` at declaration. We can add this later if needed.

We go with **A**. Because the user opted out of any coercion: `string s = 5` is an error (RHS isn't a string expression). The declaration keyword sets the expected type of the RHS, and a numeric-typed RHS at a `string` declaration is rejected with a ParseError.

### 2. Lexer & keyword reservations

Files: `src/svgdsl/dsl/lexer.py`, `src/svgdsl/interpreter.py:14`

- Double-quoted strings are already handled — `_QUOTED` at `lexer.py:19, 45–50`. No change.
- **Add single-quoted strings.** Insert:
  ```python
  _QUOTED_SINGLE = re.compile(r"'([^']*)'")
  ```
  In `tokenize()` (lexer.py:23–95), add a match block for `_QUOTED_SINGLE` **between** the existing `_QUOTED` block (line 45–50) and the `_PX`/`_FEET_INCHES`/`_FEET_ONLY` blocks. Both quote styles produce the same `Token("QUOTED", content, lineno)` — downstream code can't tell them apart, which is correct.
  - *Why this is safe:* `_FEET_INCHES = r"(\d+)'(\d+)\"?"` and `_FEET_ONLY = r"(\d+(?:\.\d+)?)'"` both require a digit *before* the `'`. The tokenizer matches anchored at position `i`. When `raw[i] == "'"`, neither feet pattern can fire — so a leading `'` at any token boundary is unambiguous as a string opener.
  - Escape processing matches double-quoted strings: `\n` → newline (line 47 pattern).
- Add `string` to `_ALL_KEYWORDS` in `interpreter.py:14`. Reserve `tuple` and `numeric` at the same time for forward compatibility.
- Add a reserved-builtin set: `{"len", "substr", "match", "replace"}` — checked when validating variable assignments to prevent shadowing.

### 3. Parser / interpreter changes

File: `src/svgdsl/interpreter.py`

#### 3a. Declaration syntax — extend `_execute_stmt`

Today (interpreter.py:300–330) the dispatcher checks `parts[0]` against `_ALIASES`/keywords, then falls through to `_ASSIGNMENT_RE`. Insert a new branch *before* the existing assignment match:

```python
_DECL_RE = re.compile(
    r'^(string|numeric)\s+'
    r'([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)'   # name list
    r'\s*(?:=\s*(.+))?$'
)
```

The name list may be a single identifier or a comma-separated list. The `= expr` portion is optional.

Cases the handler must support:
- `string s` → `vars_["s"] = ""` (empty string default).
- `numeric x` → `vars_["x"] = 0.0` (matches existing implicit-zero behavior for `+=`/`-=` at interpreter.py:324–325).
- `string a, b, c` → each of `a`, `b`, `c` gets `""`.
- `numeric a, b, c` → each of `a`, `b`, `c` gets `0.0`.
- `string s = expr` → evaluate RHS via `_eval_string_expr` (§3c), store the resulting `str`.
- `numeric x = expr` → existing numeric eval path, store `float`. (Provided for symmetry; optional for authors.)
- `string a, b = "x"` → **ParseError** (`"multi-declaration cannot have an initializer"`). Parallel-assignment semantics are deferred; an author who needs initial values writes one declaration per line.

Validate that each name isn't reserved/keyword as today (interpreter.py:314–317). Validate that names aren't duplicated within the same declaration (`string a, a` → ParseError).

#### 3b. Plain assignment — type-dispatch on the RHS

The existing `_ASSIGNMENT_RE` branch (interpreter.py:311–330) needs to recognise when the RHS is a string-typed expression:

- If the variable already exists in `vars_` and is a `str`, treat the RHS as a string expression (so `s = s + " more"` works).
- Else if the RHS, after `_substitute_vars`, *starts with a quoted literal*, treat it as a string expression.
- Else: existing numeric path.

`+=` on an existing string variable performs string concatenation; `-=` on a string is a type error.

#### 3c. String expression evaluator — new `_eval_string_expr`

Replaces a string-mode RHS like `"hello" + " " + name` with a single Python string. Approach:

1. Token-scan the expression into a flat list of (literal | varref | `+` operator | builtin-call).
2. Resolve each varref against `vars_`; if the value is `float`, **raise** — no coercion.
3. Resolve builtin calls (`len`, `substr`, `match`, `replace`) via a small dispatch dict — thin wrappers over Python `len`, slicing, `re.search`, `re.sub`. (`len` and `match` return numeric/bool and so cannot legally appear in a string-position fold; they are valid only when the *result* feeds a numeric context. The evaluator rejects them as direct operands of string `+`.)
4. Fold `+` across the resulting list of strings; any non-string operand → ParseError.

Critical: do **not** route this through `eval()`. The existing `_eval_expr` uses `eval` with restricted builtins (interpreter.py:460), which is fine for numerics but unsafe to extend to arbitrary string operations. The string evaluator is a small custom interpreter — ~60 lines.

#### 3d. Inline `(...)` evaluation inside quoted contexts

Today `_evaluate_inline_exprs` (interpreter.py:396–436) skips over content inside `"..."`. That stays — inside a string literal, `(x+1)` is *not* evaluated. To interpolate, the author writes `"x = " + str(x+1)`. This matches the conservative behavior and avoids a templating language.

#### 3e. Variable substitution `${name}` already works for strings

`_substitute_vars` (interpreter.py:386–393) already returns the raw string when `isinstance(val, str)`. No change needed — `label "${title}"` already works for string variables once they can be assigned.

### 4. Built-in functions

New module: `src/svgdsl/dsl/builtins.py`

```python
def _builtin_len(s: str) -> int: return len(s)
def _builtin_substr(s: str, start: int, end: int | None = None) -> str: ...
def _builtin_match(s: str, pattern: str) -> bool:    # re.search → 1/0
def _builtin_replace(s: str, pattern: str, repl: str) -> str:  # re.sub

BUILTINS = {
    "len":     _builtin_len,
    "substr":  _builtin_substr,
    "match":   _builtin_match,
    "replace": _builtin_replace,
}
```

Per the user's "hard error, no conversion" choice, there are **no** `str()` or `num()` builtins.

Wire into numeric context: when `_eval_expr` (or its caller) sees `len(varname)` or `match(varname, "...")`, the builtin must be invoked before the expression reaches Python's `eval`. Simplest path: pre-scan `expr` in `_evaluate_inline_exprs` (interpreter.py:396–436) for builtin-call patterns and substitute the result before falling through to `_eval_expr`. This keeps `_eval_expr` itself unchanged.

### 5. Type-error reporting

All type errors raise `ParseError(f"Line {lineno}: ...")` so they integrate with the existing error path (interpreter.py:9). Messages:
- `"variable 'x' is a string, not numeric"` (already exists at line 451 — reuse)
- `"cannot concatenate numeric and string"` (no suggested fix — there is no conversion builtin; the author must restructure)
- `"len/substr/match/replace expect a string argument"`

### 6. Anticipating tuple

The declaration regex is already shaped for an open type set; adding `tuple` is `_DECL_RE` extension + a new evaluator that produces a list/tuple stored in `vars_` (the type union becomes `float | str | tuple`). Function-call form (`size(t)`, `at(t, i)`) means no new operator syntax to invent. **No further commitments here** — tuples are a separate plan; we just verify nothing in this plan blocks them.

## Files to modify

| File | Change |
|---|---|
| `src/svgdsl/interpreter.py` | Add `_DECL_RE`, declaration branch in `_execute_stmt`, string-aware path in `_ASSIGNMENT_RE`, new `_eval_string_expr`, builtin pre-scan in `_evaluate_inline_exprs`, reserved keywords (`string`, `tuple`, `numeric` plus builtin names) added to `_ALL_KEYWORDS`. |
| `src/svgdsl/dsl/builtins.py` | **New file.** `BUILTINS` registry — `len`, `substr`, `match`, `replace`. |
| `src/svgdsl/dsl/lexer.py` | Add `_QUOTED_SINGLE` regex and a match block in `tokenize()` between `_QUOTED` and `_PX` — produces the same `Token("QUOTED", ...)` shape so downstream consumers are unchanged. |
| `docs/design-guide.md` | Add a "Strings and explicit types" section after the existing Variables section (around line 99–156). Document `string s = "..."`, operators, builtins, the no-implicit-coercion rule. |
| `docs/statements-and-tokens.md` | Add the `string` keyword and the declaration form to the statement grammar. |
| `docs/users-guide.md` | Worked examples — labels built from string concat, regex replace for filename sanitisation. |
| `drawings/string_test.dsl` | **New file.** Smoke-test all four builtins plus `+`/`+=`. |

## Existing utilities to reuse

- `ParseError` (`src/svgdsl/dsl/parser.py`, imported at `interpreter.py:9`) — all new errors raise this.
- `_substitute_vars` (`interpreter.py:386–393`) — string-aware already.
- `_VARREF_RE` (`interpreter.py:26`) — same `$name`/`${name}` syntax for string vars; no new ref form needed.
- `vars_` symbol table (`interpreter.py:53`) — already `float | str` union; tuple slot opens later by widening this.
- `_fmt_float` (`interpreter.py:373–383`) — keeps `${x}` interpolation into labels scientific-notation-safe (the fix from #42); the string evaluator does not duplicate this logic, since numbers cannot enter a string expression directly.
- `tokenize` (`lexer.py:23`) — reused as-is for parsing builtin call arguments inside the string evaluator if needed.

## Verification

1. **Existing regression:** run every file in `drawings/*.dsl` through the CLI and diff the SVG output against committed `output.svg` — no behavioral change for current files (numeric-only paths untouched).
2. **New smoke test** — `drawings/string_test.dsl`:
   ```
   string empty                            # declaration with no initializer → ""
   string a, b, c                          # multi-declaration, all → ""
   if (len(empty) == 0) { label "empty ok" }
   a = "alpha"
   b = "beta"
   label "${a} ${b} (c is empty:${c})"
   string title = "Master Bedroom"
   string suffix = ' (rev 2)'              # exercises single-quote literal
   title += suffix
   label "${title}"
   n = (len(title))                        # numeric from string builtin
   label "len = ${n}"                      # number interpolation via existing $-substitution
   string clean = replace(title, "[^A-Za-z]", "_")
   label "${clean}"
   if (match(title, "Bedroom")) { label "match ok" }
   string sub = substr(title, 0, 6)
   label "${sub}"
   ```
   Render and verify each label appears correctly in the SVG.
3. **Type-error tests** — small inline scripts that should error cleanly:
   - `string s = "x"` then `y = s + 1` → ParseError on concat
   - `x = 5` then `string t = x` → ParseError (no coercion)
   - `string s = "abc"` then `s -= "a"` → ParseError ("-= not defined on string")
   - `string a, b = "x"` → ParseError ("multi-declaration cannot have an initializer")
   - `string a, a` → ParseError (duplicate name)
   - `wall 12'6"` continues to parse as feet/inches — confirms single-quote literal addition didn't regress measurements.
4. **RCS check-in** (per repo convention): `ci -l` each modified file after the user approves the implementation.

## Out of scope

- Numeric ↔ string conversion builtins (`str()`, `num()`) — per user decision, mismatches are hard errors. Authors interpolate numbers into labels via the existing `${var}` syntax.
- String interpolation expressions inside `"..."` (e.g. `"x = ${x+1}"`) — author uses `+` and plain `${var}` substitution.
- Tuple data type — separately planned; this design just stays compatible (`tuple` keyword reserved now).
- Mutable string indexing (`s[0] = "x"`) — not in issue #38; strings remain immutable values.
