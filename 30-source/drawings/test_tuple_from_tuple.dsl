# issue #55 acceptance test
tuple a = (1, 2)
tuple b = (3, 4)
tuple c = a, b           # (1, 2, 3, 4)
tuple d = (a, b)         # (1, 2, 3, 4)
tuple e = (0, a, 5)      # (0, 1, 2, 5)
tuple f = ($a, $b)       # (1, 2, 3, 4)
tuple g = a + b          # (4, 6) — element-wise still works
tuple h = (a[0], 5)      # (1, 5) — indexing still works
vardump
