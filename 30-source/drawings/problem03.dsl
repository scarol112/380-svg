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

textbox 2 2 A=7,4 "1. Now is the time for all good men to come to the aid of their party.\n" @messages


tapp "2. appended1\n" messages
tapp "3. appended2\n" C=red messages
tapp "4. appended2\n" C=red messages
tapp "5. appended2\n" C=red messages
tapp "6. Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua." messages 

include grid10x8.dsl
include border.dsl

