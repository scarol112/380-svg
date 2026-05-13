# Master Bedroom
include page-letter-landscape-def.dsl

dir 90
dim on
l 24.5" A=0,0
window 6'5"
l 49.5"

dir 180
l 115"
# door i and swing
l 30"0px
cx1=$__cx; cy1=$__cy
#mto $__cx ($__cy + 2.5)

lto ($__cx - 2.6) ($__cy + 0.42) dashed dim=off
#arc 30" 90 start=270 dashed dim=off
mto ($__cx - .75) ($__cy - 1.25); dir 90
# arrow to hallway
aw 1.5 3px dim=off; l 0.25 0px; lb 12 "Hallway"
mto $cx1 $cy1

dir 180
l 67.5"

dir 270
l 58" 
# door to bath
l 30" 0px
cx1=$__cx; cy1=$__cy
mto ($cx1 + 1.25) ($cy1 - 2)
dir 180; aw 1.5 3px dim=off; l 0.35 0px; lb 12 "Bathroom"
dir 270
mto $cx1 $cy1
l 63"

dir 0; l 29"
dir 270; l 33"
dir 0; l 135"
dir 90; l 33"
dir 0; l 48.2"
 
# desk
dim off
color darkorange
mto (12.58-5.25) (0.25)
dir 90; l 5'; dir 180; l 75"
dir 270;l 28"
dir 0; l 4'; dir 270; l 32"
dir 0; l 27"
color black

dir 90
mto 5 7; p 0px C=red dim=off @p1; textline center 18 "Master Bedroom" p1
mto 0 8; include rulerh10.dsl
