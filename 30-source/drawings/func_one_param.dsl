# func_one_param.dsl — numeric param binding

def draw_box(sz) {
    mto 1,1
    r $sz $sz
}

draw_box(2)

lb 0.2,0.5 12 "one-param function ran"
