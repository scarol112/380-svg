# func_return_tuple.dsl — tuple return feeding an unpack

def make_point(x, y) {
    return (x, y)
}

(px, py) = make_point(3, 7)
lb 0.5,1 14 "px=3 py=7"
vardump
