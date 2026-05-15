# func_recursion_overflow.dsl — self-call to depth 256; expect ParseError

def infinite(n) {
    return infinite((n + 1))
}

# This should raise: maximum recursion depth (256) exceeded
numeric x = infinite(0)
