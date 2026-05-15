# func_scope_isolation.dsl — local writes don't leak; __cursorx mutation does

numeric x = 100
numeric y = 200

def modify_locals() {
    numeric x = 999
    numeric y = 888
    mto 3,3
}

modify_locals()

# x and y should still be 100 and 200
# __cursorx should be 3 after mto 3,3 inside the function
lb 0.5,0.5 12 "x=100 y=200 after function"
vardump
