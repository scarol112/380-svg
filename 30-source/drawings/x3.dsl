include page-tabloid-landscape-def.dsl

r $xmax $ymax A=0,0

lb 24 C=green "Big Page" A=3,3

lto $xmax 0 0px  A=0,0 @l1
textbreak 0px "$xmax" l1
dir 180
    lto $xmax $ymax 0px A=$xmax,0 @l2
    textbreak 0px "$ymax" l2
dir 90

mto 5 4; circle 0.4  C=green dashed

lb "__dir = $__dir" A=5,5 C=red

mto 0 ($ymax/2)
include rulerh10.dsl
dir 180
mto ($xmax/2) 0
include rulerv8.dsl
dir 90
