eid off
dimensions off

include grid10x8-halfs.dsl
color black
pxmax=10; pymax=8
r $pxmax $pymax  0px A=0,0 @page
textbox 2 8 A=0,0 " " @log
textbreak font=papyrus 14 0px " Log " log

# Viewport mockup w horiz lines red
r 1 3 1px A=7.5,0.5 C=gray
l 1   0px A=7.5,0.5 @l751; textbreak 11 right 0px "Viewport" l751
r 0.5 2 A=7.75,1.0
l 0.5 A=7.75,1.2; l 0.5 A=7.75,1.4; l 0.5 A=7.75,1.6; l 0.5 A=7.75,1.8; l 0.5 A=7.75,2.0
l 0.5 A=7.75,2.2; l 0.5 A=7.75,2.4; l 0.5 A=7.75,2.6; l 0.5 A=7.75,2.8; l 0.5 A=7.75,3.0

textbox 2 2 A=7,4 " " @messages
textbreak font=papyrus 14 0px " Messages " messages

x=3; y=1
tapp "x= ${x}, y= ${y}" messages

for i=0.5 to 7.5 step 0.5 {
    tapp "${i} loop ${x}, ${y}" log
    l 0.5 2px C=darkorange A=${x},${i}
#     l 0.05 0px; lb 10 "   ${y}"
#     for j=1 to 12 step 3 {
#     tapp ". . . . $i , $j" log
#     }
    y+=0.2
} 

p 20px A=5,5 @r1
textline "test" r1












# ================================================================
# info box
dir 90
mto 7 7; rect 3 1
l 1 0px A=9,7 @l97; textbreak 10 right 0px "$__dsl_filename" l97
l 2.95 0px A=7,8 @baseline; textline 10 right "$__date" baseline
lb A=7.05,7.2 16 "Element Examples"

#include grid20x16.dsl
#include border.dsl
mto 0 7.5
# include rulerh10.dsl
