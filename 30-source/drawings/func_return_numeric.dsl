# func_return_numeric.dsl — call in (…) arithmetic

def double(x) {
    return (x * 2)
}

numeric result = (double(5) + 1)
lb 0.5,1 14 "double(5)+1 should be 11"
vardump
