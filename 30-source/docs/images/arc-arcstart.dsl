# Four arcs at different arcstart angles (sweep 90 each, radius 2)
eid off; dim off
textstyle 9 normal

# Arc 1: arcstart=0 (start at 12 o'clock, sweep to 3 o'clock)
point C=red A=4,4
arc 2 90 arcstart=0 2px A=4,4
label "arcstart=0" A=2.5,1.5 C=blue

# Arc 2: arcstart=90 (start at 3 o'clock, sweep to 6 o'clock)
point C=red A=14,4
arc 2 90 arcstart=90 2px A=14,4
label "arcstart=90" A=12.5,1.5 C=blue

# Arc 3: arcstart=180 (start at 6 o'clock, sweep to 9 o'clock)
point C=red A=4,12
arc 2 90 arcstart=180 2px A=4,12
label "arcstart=180" A=2.5,9.5 C=blue

# Arc 4: arcstart=270 (start at 9 o'clock, sweep to 12 o'clock)
point C=red A=14,12
arc 2 90 arcstart=270 2px A=14,12
label "arcstart=270" A=12.5,9.5 C=blue
