# Nested if/else inside a for loop — exercises brace depth tracking
# across lines that both close and open (e.g. `} else {`).
# Expected: 2 lines drawn, total length 1+10 = 11.
n = 0
direction 90
for i = 1 to 2 {
    if (i == 1) {
        line 1
    } else {
        line 10
    }
}
