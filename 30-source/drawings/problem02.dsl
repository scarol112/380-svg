eid off
dimensions off
p 0px A=0,0
#p $__cx $__cy  20px C=maroon

r 5 3 1px A=1,4 C=red
l 5 A=1,4 C=blue @l1; textbreak "***textbreak*** Now is the time for all good men" C=maroon l1


l 5 A=2,2 @l2
textline "***textline*** text 16pt" 16 left l2
textline "*italic* 20 pt" C=blue center 20 l2
textline "**bold courier** 12pt" font=courier right 12 l2

textbox 2 2 A=7,4 "Now is the time for all good men to come to the aid of their party\n"

include grid10x8.dsl
include border.dsl

#FIXME does not wrap text in textbox
