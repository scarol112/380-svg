# func_nested_call.dsl — f(g(x)) numeric + f(substr(s,0,3)) mixed

def double(x) {
    return (x * 2)
}

def add_one(x) {
    return (x + 1)
}

# nested numeric: double(add_one(4)) == 10
numeric r1 = double(add_one(4))

# builtin inside user function arg
string s = "hello world"
string prefix = substr(s, 0, 5)

lb 0.5,1 14 "double(add_one(4)) should be 10"
vardump
