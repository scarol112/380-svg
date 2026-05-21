# Clockwise vs counter-clockwise sweep
eid off; dim off
textstyle 9 normal

# Default (clockwise) — sweep 180 from 12 o'clock → 6 o'clock via 3 o'clock
point C=red A=4,4
arc 2 180 arcstart=0 2px A=4,4
label "default: clockwise" A=2.5,1.5 C=blue

# ccw — sweep 180 from 12 o'clock → 6 o'clock via 9 o'clock
point C=red A=12,4
arc 2 180 ccw arcstart=0 2px A=12,4
label "ccw (counter-clockwise)" A=10.5,1.5 C=blue
