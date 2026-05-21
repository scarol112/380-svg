# Arc anatomy: center, radius, sweep, arcstart on one figure
eid off; dim off
textstyle 9 normal

# 1) Center marker at (5, 5)
point C=red A=5,5
label "center" right C=red A=4.7,5

# 2) Radius from center to arcstart (12 o'clock, arcstart=0)
lineto 5,3 dotted C=gray A=5,5
label "r = 2" C=gray A=5.15,4

# 3) Radius from center to the arc's end (sweep=90 clockwise → 3 o'clock)
lineto 7,5 dotted C=gray A=5,5

# 4) The arc
arc 2 90 2px A=5,5

# 5) Annotations
label "arcstart=0 (12 o'clock)" C=blue A=5.2,2.6
label "sweep = 90 (clockwise)" C=blue A=5.8,4.2
label "end" A=7.2,5
