import sys; sys.path.insert(0, sys.argv[1])
from minloss import *
def run(name, attrs, fds, w=None):
    N,S=parse(attrs,fds)
    out={}
    for mode in ("full","plain","local"):
        b,sols,Sa=solve(N,S,w=w,mode=mode)
        out[mode]=b
    print(f"{name:28s} |Sa|={len(Sa):2d} full={out['full']} plain={out['plain']} local={out['local']}")
run("running example","CSTZ",["C->ST","ST->Z","Z->T"])
run("restrictions(plain)","ABCDE",["D->C","BE->C","BD->A","ABC->D"])
run("restrictions(keycompl)","ABCDE",["B->E","CE->A","CE->B","ADE->B","ABD->C"])
run("weakenings 1","ABCDE",["B->A","BC->E","BD->E","ACE->B","ADE->B"])
run("weakenings 2","ABCDE",["A->D","DE->A","AE->B","BCE->D"])
run("cover-tight","ABCDE",["A->BD","D->A","B->E","E->B","BC->A"])
attrs="ABCDEF"
N,S=parse(attrs,["DF->C","ACE->D","AE->B","AF->D","BDE->A","DE->F"])
light={"AE->B","AF->C","AF->D"}
w=lambda f: 1 if show(attrs,f) in light else 4
run("local (weighted)",attrs,["DF->C","ACE->D","AE->B","AF->D","BDE->A","DE->F"],w=w)
run("local (unit)",attrs,["DF->C","ACE->D","AE->B","AF->D","BDE->A","DE->F"])
