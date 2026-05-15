# func_noparam.dsl — def + call-as-statement; drawing inside body

def draw_cross() {
    mto 1,1
    l 1 0px
    mto 1.5,0.5
    dir 0
    l 1 0px
}

draw_cross()

lb 0.2,0.5 12 "no-param function ran"
