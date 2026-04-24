# Simple floor plan test — two rooms
direction 90
rect 12 10 "Living Room"
rect 10 10 "Bedroom"
line 5 2px A=24,6
direction 180
line 5

# Door in living room bottom wall
door 3 right A=2,10

# Window on bedroom right wall
window 4 A=22,3

direction 90
dimensions off
elementid off
line 1 2px A=0,-10
line 1 0px
line 1 2px
line 1 0px
elementid on
line 1 2px
line 1 0px
line 1 2px
line 1 0px
