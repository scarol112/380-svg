# func_multi_param.dsl — mixed numeric + string params

def annotated_box(w, h, lbl) {
    mto 1,1
    r $w $h
    lb 1.1,1.5 10 $lbl
}

annotated_box(3, 2, "box label")

lb 0.2,0.5 12 "multi-param function ran"
