#tag 200x200 grid test
r 200 200
r 90 150 a=5,5
r 90 150 a=105,5
r 190 35 a=5,160
s = "Now is the time for all good men to come to the aid of their party."
ls = len(s)
lb "$s" a=10,10 c=black
lb "${ls}" a=(10+(ls/2)),15 c=black
grid_xmax=200; grid_ymax=200;grid_size = 5;showvalues=False
inc grid.dsl

