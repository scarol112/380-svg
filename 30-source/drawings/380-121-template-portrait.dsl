#tag template portrait test
# template
include page-letter-portrait-def.dsl

mto 7 7; r 3 1 A=7,7
l 1 0px A=9,7 @l97; textbreak 10 right 0px "$__dsl_filename" l97
l 2.95 0px A=7,8 @baseline; textline 10 right "$__date" baseline
lb A=7.05,7.2 16 "Template"

mto 0 0
grid_size=0.5 ; include grid.dsl
mto 0 4       ; include ruler.dsl
mto 5 0       ; include rulerv8.dsl
include border.dsl
