# test_tuple_extract.dsl — extract a string element from a tuple
tuple paper = ("letter", "landscape")
string pname = paper[0]
string porient = paper[1]
lb 0.5,1 14 "pname=${pname}  porient=${porient}"
vardump
