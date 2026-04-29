# Issue #20 variable test
roomw = 12
roomh = 8
lw = 2
offset = 2

dir 90
rect $roomw $roomh "${roomw}x${roomh} ft room"
door 3 ${lw}px A=$offset,$roomh
point C=red A=$cursorx,$cursory
