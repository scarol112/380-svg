# ctrl_for_include.dsl — include inside a for loop
direction 90
for i = 1 to 3 {
    yl = $i
    include circlerow.dsl
}
