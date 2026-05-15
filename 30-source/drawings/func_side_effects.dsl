# func_side_effects.dsl — call in expression both draws AND returns

def draw_and_return(x) {
    mto $x,1
    l 1 0px
    return (x * 10)
}

# call-as-statement: draws, return value discarded
draw_and_return(1)

# call in assignment: draws again, return value used
numeric result = draw_and_return(2)

lb 0.5,0.5 12 "result should be 20"
vardump
