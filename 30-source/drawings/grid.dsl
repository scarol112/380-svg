# 10x8 unit grid
dir 90
color Gainsboro

showvalues = False
grid_xmax = 10
grid_ymax = 8
grid_size = 1

r $grid_xmax $grid_ymax A=0,0

stop = $grid_ymax - $grid_size
for y=$grid_size to $stop step $grid_size {
    l 10 A=0,$y
    if ($showvalues) {
        lb "$y"
    }
}

dir 180
stop = $grid_xmax - $grid_size
for x=$grid_size to $stop step $grid_size {
    l 8 A=$x,0
    if ($showvalues) {
        lb "$x"
    }
}

mto 0 0
dir 90
