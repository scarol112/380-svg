# issue #52 acceptance test
string s = "hello"
b = s              # bare ref to string var → should be S "hello"
c = $s             # $-ref to string var → should be S "hello"
d = "world"        # literal → still works
tuple t = (1,2)
t2 = t             # bare tuple ref → still works
numeric n = 5
n2 = $n            # $-ref numeric → still works
n3 = n             # bare numeric ref → should be N 5 (NEW)
vardump
