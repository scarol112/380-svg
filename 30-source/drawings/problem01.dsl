eid off
dimensions off
sxy on
l 3 A=1,1
#p $__cx $__cy  20px C=maroon

r 5 3 1px A=1,4 C=red
l 5 A=1,4 C=blue @l1; textbreak "Now is the time for all good men" font=courier l1


l 5 A=2,2 @l2
textline "longer text 16pt" 16 left l2
textline "*italic text* 20 pt" center 20 l2
textline "**bold longer text** 12pt" right 12 l2

include grid10x8.dsl
include border.dsl

#FIXME chops red rectangle
