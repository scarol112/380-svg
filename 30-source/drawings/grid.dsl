# 10x8 (default) unit grid with 1 (default) unit squares
dir 90
color Gainsboro

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
#showvalues = True


r $grid_xmax $grid_ymax A=0,0

stop = $grid_ymax - $grid_size
for y=$grid_size to $stop step $grid_size {
    l $grid_xmax ${grid_stroke}px A=0,$y
    if ($showvalues) {
        lb "$y"
    }
}

dir 180
stop = $grid_xmax - $grid_size
for x=$grid_size to $stop step $grid_size {
    l $grid_ymax ${grid_stroke}px  A=$x,0
    if ($showvalues) {
        lb "$x"
    }
}

mto 0 0
dir 90
