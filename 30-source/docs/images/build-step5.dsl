eid on; dim on
livingw = 12
bedw    = 8
roomh   = 10
wallt   = 0.5

wall (livingw + bedw) $wallt
rect $livingw $roomh "Living"
rect $bedw    $roomh "Bedroom"
door 3 right A=2,$roomh
window 4 A=(livingw + 3),$roomh
