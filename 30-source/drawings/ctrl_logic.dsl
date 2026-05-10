# ctrl_logic.dsl — logical operators and True/False
flag = True
n = 3
direction 90
if (flag and not (n > 5)) {
    color blue
    line 5
} else {
    color green
    line 5
}
# flag should evaluate to 1.0 (True), n>5 is false, so not(false)=true → blue line
