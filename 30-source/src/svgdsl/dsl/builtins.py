import re

from .parser import ParseError


def _check_str(name: str, arg: object, lineno: int) -> str:
    if not isinstance(arg, str):
        raise ParseError(f"Line {lineno}: {name}() expects a string argument")
    return arg


def _check_int(name: str, arg: object, lineno: int) -> int:
    if not isinstance(arg, (int, float)):
        raise ParseError(f"Line {lineno}: {name}() expects a numeric argument")
    return int(arg)


def builtin_len(args: list[object], lineno: int) -> float:
    if len(args) != 1:
        raise ParseError(f"Line {lineno}: len() takes 1 argument, got {len(args)}")
    s = _check_str("len", args[0], lineno)
    return float(len(s))


def builtin_substr(args: list[object], lineno: int) -> str:
    if len(args) not in (2, 3):
        raise ParseError(f"Line {lineno}: substr() takes 2 or 3 arguments, got {len(args)}")
    s = _check_str("substr", args[0], lineno)
    start = _check_int("substr", args[1], lineno)
    if len(args) == 3:
        end = _check_int("substr", args[2], lineno)
        return s[start:end]
    return s[start:]


def builtin_match(args: list[object], lineno: int) -> float:
    if len(args) != 2:
        raise ParseError(f"Line {lineno}: match() takes 2 arguments, got {len(args)}")
    s = _check_str("match", args[0], lineno)
    pat = _check_str("match", args[1], lineno)
    try:
        return 1.0 if re.search(pat, s) else 0.0
    except re.error as e:
        raise ParseError(f"Line {lineno}: invalid regex in match(): {e}")


def builtin_replace(args: list[object], lineno: int) -> str:
    if len(args) != 3:
        raise ParseError(f"Line {lineno}: replace() takes 3 arguments, got {len(args)}")
    s = _check_str("replace", args[0], lineno)
    pat = _check_str("replace", args[1], lineno)
    repl = _check_str("replace", args[2], lineno)
    try:
        return re.sub(pat, repl, s)
    except re.error as e:
        raise ParseError(f"Line {lineno}: invalid regex in replace(): {e}")


BUILTINS = {
    "len":     builtin_len,
    "substr":  builtin_substr,
    "match":   builtin_match,
    "replace": builtin_replace,
}

BUILTIN_RETURNS_STRING = {"substr", "replace"}
BUILTIN_RETURNS_NUMERIC = {"len", "match"}
