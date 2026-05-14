# 10x8 (default) unit grid with 1 (default) unit squares

dir 90
color Gainsboro

# future ===========
grid_bounds = 0,0,10,8
tuple grid_center = (grid_bounds[2],grid_bounds[3]) / 2
showvalues = True
grid_xmax=20
grid_ymax=16
grid_size =0.25 
# future ===========

if ($grid_size == 0) {
    grid_size = 1
    }
if ($grid_xmax == 0) {
    grid_xmax = 10
    }
if ($grid_stroke == 0) {
    grid_stroke = 1
    }
if ($grid_ymax == 0) {
    grid_ymax = 8
    }


r $grid_xmax $grid_ymax A=0,0

maxval = $grid_ymax - $grid_size
for y=$grid_size to $maxval step $grid_size {
    l $grid_xmax ${grid_stroke}px A=0,$y
    if ($showvalues) {
        lb "$y" c=red a=(($__cx - 0.25), $y)
    }
}

dir 180
if (showvalues) {
    lb "${grid_size} units" 9 c=red a=(0,(${grid_ymax} + 0.4))
}
maxval = $grid_xmax - $grid_size
for x=$grid_size to $maxval step $grid_size {
    l $grid_ymax ${grid_stroke}px  A=$x,0
    if ($showvalues) {
        lb "$x" c=red
    }
}

mto 0 0
dir 90

stop
# future ===========
mto $grid_center
dir 90
lb 12 c=red "pgrid_bounds = $grid_bounds"
p 2px x=red a=($__cursor - (0.75,0))
# future ===========
