# Line style demonstration

dir 90

eid off
dim off

# solid (default)
lb "solid" left A=0,0
l 12 A=4,0.2

# dashed
lb "dashed" left A=0,1.5
l 12 dashed A=4,1.7

# shortdash
lb "shortdash" left A=0,3
l 12 shortdash A=4,3.2

# dotted
lb "dotted" left A=0,4.5
l 12 dotted A=4,4.7

# center
lb "center" left A=0,6
l 12 center A=4,6.2

# hidden
lb "hidden" left A=0,7.5
l 12 hidden A=4,7.7
