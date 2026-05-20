#tag Master Bedroom floorplan
# ==============
# Master Bedroom
# ==============
include page-letter-landscape-def.dsl

dim on
p 0 0 C=green
dir 90

# ----- Window wall -----
l 24.5" A=0,0
window 6'5"
l 49.5"

# ----- Hallway wall -----
dir 180
l 115"
# door and swing
l 30"0px
cx1=$__cx; cy1=$__cy

lto ($__cx - 2.6) ($__cy + 0.42) dashed dim=off
mto ($__cx - .75) ($__cy - 1.25); dir 90
aw 1.5 3px dim=off; l 0.25 0px; lb 12 "Hallway"
mto $cx1 $cy1


dir 180
l 67.5"

# corner height
cx1=$__cx; cy1=$__cy
mto ($cx1 - 0.083) ($cy1 - 2.083)
l 2 dashed dim=off; dir 270; l 2 dashed dim=off
mto ($cx1 + 0.083) ($cy1 - 1)
dir 90;l 1 dotted; l 0.1 0px; lb "corner height\n58in"

mto $cx1 $cy1

# ----- Bathroom wall ----- 
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
cx2=$__cx; cy2=$__cy

# corner height
cx1=$__cx; cy1=$__cy # 0, ymax
mto ($cx1 + 0.083) ($cy1 - 2.083)
dir 180; l 2 dashed dim=off; dir 90; l 2 dashed dim=off
mto ($cx1 - 0.083) ($cy1 - 1)
dir 270;l 1 dotted; l 0.1 0px; lb "corner height\n75in" A=($__cx - 1.4),$__cy

mto $cx1 $cy1

# ----- Outside wall -----
dir 0; l 29"
dir 270; l 33"
dir 0; l 135"
    rulerpoint = $__cursor
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

# existing table
dir 90
r 39.5" 20" A=3.5,0.25

# Tall table from DR
dir 90
w = (22/12) ; l = 5
r 60" 22" A=($cx2 + 0.13),($cy2 - 2.03)

color black
dir 90

# Decorations
mto 5 7; p 0px C=red dim=off @p1; textline center 18 "Master Bedroom" p1

mto ($rulerpoint + 0,5); rulerlength=16; include ruler.dsl








#end
