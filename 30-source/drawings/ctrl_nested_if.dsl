# Nested if/elif/else chain — outer if contains an inner if/elif/else chain.
# Tests that _find_matching_close correctly tracks depth across `} elif {` and
# `} else {` lines at nested depth.
a = 1
b = 2
direction 90
if (a == 1) {
    if (b == 1) {
        line 1
    } elif (b == 2) {
        line 2
    } else {
        line 99
    }
} else {
    line 50
}
# Expected: 1 line of length 2 (a==1 branch, b==2 branch)
