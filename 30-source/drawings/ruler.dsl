# variable length, direction, divisions ruler

if ($rulerlength == 0) {
l = 10
} else {
l = $rulerlength
}

if ($rulerdivisions == 0) {
r =0.5 
} else {
r = $rulerdivisions
}


if ($rulerdirection == 0) {
d = 90
} else {
d = $rulerdirection
}


rulerOx = $__cx; rulerOy = $__cy # ruler Origin
dir $d
for i = 1 to $l {
tick = ($i * $r)
tick2 = ($tick * 2)
l $r

l $r 4px 
cx1=$__cx; cy1=$__cy
shiftx=($__cx - ($r / 1.3)); shifty=($__cy - 0.05)
lb "${tick2}" A=$shiftx,$shifty
mto $cx1 $cy1
}

