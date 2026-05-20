# Viewport mockup w horiz lines
r 1 3 1px A=7.5,0.5 C=gray
l 1   0px A=7.5,0.5 @l751; textbreak 11 right 0px "Mock Viewport" l751

r 0.5 2 A=7.75,1.0

l 0.5 A=7.75,1.2; l 0.5 A=7.75,1.4; l 0.5 A=7.75,1.6; l 0.5 A=7.75,1.8; l 0.5 A=7.75,2.0
l 0.5 A=7.75,2.2; l 0.5 A=7.75,2.4; l 0.5 A=7.75,2.6; l 0.5 A=7.75,2.8; l 0.5 A=7.75,3.0

mto 7 7; rect 3 1
l 1 0px A=9,7 @l97; textbreak 10 right 0px "$__dsl_filename" l97
l 2.95 0px A=7,8 @baseline; textline 10 right "$__date" baseline
lb A=7.05,7.2 16 "Drawing Title"

grid_size=1 ; include grid.dsl
mto 0 4     ; include ruler.dsl
mto 5 0     ; rulerlength=8; rulerdirection=180; include ruler.dsl; dir 90
