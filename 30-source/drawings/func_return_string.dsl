# func_return_string.dsl — string return into a string var

def greet(name) {
    return "Hello, " + name
}

string msg = greet("World")
lb 0.5,1 14 $msg
vardump
