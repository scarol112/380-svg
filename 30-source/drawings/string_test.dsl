# Smoke test for string data type (issue #38).
# Exercises: single/multi declarations, both quote styles, + / +=,
# len, substr, match, replace, ${...} interpolation.

direction 90

string empty
string a, b, c

if (len(empty) == 0) {
    label "empty ok"
}

a = "alpha"
b = "beta"
label "${a} ${b} [c is empty:${c}]"

string title = "Master Bedroom"
string suffix = ' (rev 2)'
title += suffix
label "${title}"

n = (len(title))
label "len = ${n}"

string clean = replace(title, "[^A-Za-z]", "_")
label "${clean}"

if (match(title, "Bedroom")) {
    label "match ok"
}

string sub = substr(title, 0, 6)
label "${sub}"
