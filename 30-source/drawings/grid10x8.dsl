# 10x8 unit grid with 1 unit squares
dir 90
color Gainsboro
r 10 8 A=0,0

grid_size = 1
showvalues = True

stop = 8 - $grid_size
for y=$grid_size to $stop step $grid_size {
    l 10 A=0,$y
    if ($showvalues) {
        lb "$y"
    }
}

dir 180
stop = 10 - $grid_size
for x=$grid_size to $stop step $grid_size {
    l 8 A=$x,0
    if ($showvalues) {
        lb "$x"
    }
}

mto 0 0
dir 90
