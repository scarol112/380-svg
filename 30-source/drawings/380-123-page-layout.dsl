# page layout
# requires page = (page size, orientation)
vartrace
# testing
page = ("letter","landscape")

string m
psize,porient = page

if ($psize == "letter") {
    w,l = 8.5,11
} elif ($psize == "tabloid") {
    w,l = 11,17
} else {
    m += $psize + " - unknown page size"
    lb 12 "$m" c=red a=8,8.25
}

if ($porient == "landscape") {
    w,l = l,w
}


# physical
pgheight   = $l
pgwidth    = $w
margin     = 0.5

# Visible
pgxmax     = $pgwidth  - (2*$margin)
pgymax     = $pgheight - (2*$margin)
xmax       = $pgxmax
ymax       = $pgymax

 mto 0 0
r $xmax $ymax
