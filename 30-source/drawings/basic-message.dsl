# Basic message output
include page-letter-landscape-def.dsl

mto 0 0; include border.dsl

textbox 3 7 " " A=0.5,0.5 @m
textbreak 12 0px " m " m

d= 1
D= 2
tapp "d = $d , D = $D " m

x = (1 > 2); tapp "x = $x " m

tapp "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum. " m

lb "$__dsl_filename" A=9,7.9

#rulerdivisions=0.5
#rulerlength=5
#for d = 10 to 360 step 10 {
#    mto 5 5
#    rulerdirection=$d
#   include ruler.dsl
#}

# string type tests

tapp "----------------" m
s = "hello world"
s1 = (len(s) - 2)
string s2 = $s + " today"
n = len(s)
re="h.d"
if (match(s, re)) {
   tapp "--- $s matches $re" m
} else {
   tapp "--- $s DOES NOT match $re" m
}

tapp "----------------" m
string s04 = substr(s,3,s1)
tapp "$s substr $s04" c=red m
string s05 = replace(s, "l","x")
tapp "$s  -becomes- $s05" c=red m


numeric a, b, c
string d, e, f
