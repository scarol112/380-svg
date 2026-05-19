# type inference from a string variable reference
string a = "hello"
b = a              # bare ref to string var
c = $a             # $-ref to string var
tuple t1 = (1,2)
t2 = t1            # bare ref to tuple var
t3 = $t1           # $-ref to tuple var
vardump
