# test: string slot used in concat, and inside (expr) for numeric tuple
tuple paper = ("letter", "landscape")
string msg = "paper: " + paper[0] + " / " + paper[1]
tuple nums = (3, 7)
numeric sum = (nums[0] + nums[1])
vardump
