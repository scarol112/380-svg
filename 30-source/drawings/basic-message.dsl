# Basic message output
include page-letter-landscape-def.dsl

mto 0 0; include border.dsl

textbox 3 7 " " A=0.5,0.5 @messages
textbreak 12 0px " Messages " messages

d= 1
D= 2
tapp "d = $d , D = $D " messages
