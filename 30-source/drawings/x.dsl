eid off
dimensions off
#p $__cx $__cy  20px C=maroon

r 5 3 1px A=1,4 C=red
l 5   0px A=1,4 @l1; textbreak 11 right 0px "Viewport" l1

r 1 3 1px A=7.5,0.5 C=gray
l 1   0px A=7.5,0.5 @l751; textbreak 11 right 0px "Viewport" l751
r 0.5 2 A=7.75,1.0
l 0.5 A=7.75,1.2; l 0.5 A=7.75,1.4; l 0.5 A=7.75,1.6; l 0.5 A=7.75,1.8; l 0.5 A=7.75,2.0
l 0.5 A=7.75,2.2; l 0.5 A=7.75,2.4; l 0.5 A=7.75,2.6; l 0.5 A=7.75,2.8; l 0.5 A=7.75,3.0

l 5 A=2,2 @l2
textline "***textline*** text 16pt" 16 left l2
textline "*italic* 20 pt" C=blue center 20 l2
textline "**bold courier** 12pt" font=courier right 12 l2

textbox 2 2 A=7,4 " " @messages

#textbox 2 2 A=7,4 "\nNow is the time for all good men to come to the aid of their party. Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum." @messages
textbreak font=papyrus 14 0px " Messages " messages


tapp "**APPENDED1**" font=Courier messages
tapp "appended2" messages
tapp "File: ${__dsl_filename}, line: $__dsl_file_lineno" messages
tapp "File: ${__dsl_filename}, line: $__dsl_file_lineno" messages
tapp "File: ${__dsl_filename}, line: $__dsl_file_lineno" messages
tapp "File: ${__dsl_filename}, line: $__dsl_file_lineno" messages; tapp "$__dsl_file_lineno" messages

mto 7 7; rect 3 1
l 1 0px A=9,7 @l97; textbreak 10 right 0px "$__dsl_filename" l97
l 2.95 0px A=7,8 @baseline; textline 10 right "$__date" baseline
lb A=7.05,7.2 16 "Element Examples"

# include grid10x8-halfs.dsl
#include grid20x16.dsl
include border.dsl
mto 0 7.5
# include rulerh10.dsl
