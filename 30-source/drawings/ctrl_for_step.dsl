# ctrl_for_step.dsl — countdown from 10 to 0 step -2 → 6 iterations
# After loop x should be 0
direction 90
for x = 10 to 0 step -2 {
    line 1
}
# x persists: draw a line of length x (should be 0, i.e. invisible)
line $x
