# ctrl_bare_block.dsl — bare braces for grouping; var visible outside
direction 90
{
    myvar = 42
    line 3
}
# myvar should be 42 here — no new scope
line $myvar
