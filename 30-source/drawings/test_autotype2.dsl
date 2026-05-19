# edge cases for auto-type
a = "hello"
a = a + " world"       # string += via plain assignment
b = (10, 20)
b += (1, 2)            # tuple +=
c = 5
c = c + 3              # numeric reassign
d = "first"
d = "second"           # reassign string
e = (1,2)
e = (3,4)              # reassign tuple
vardump
