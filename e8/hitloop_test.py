import sys, random, itertools; sys.path.insert(0, sys.argv[1])
from minloss import *
from hitloop import hitloop
cases=[("running","CSTZ",["C->ST","ST->Z","Z->T"]),
("restr plain","ABCDE",["D->C","BE->C","BD->A","ABC->D"]),
("restr keycompl","ABCDE",["B->E","CE->A","CE->B","ADE->B","ABD->C"]),
("weak1","ABCDE",["B->A","BC->E","BD->E","ACE->B","ADE->B"]),
("weak2","ABCDE",["A->D","DE->A","AE->B","BCE->D"]),
("cover-tight","ABCDE",["A->BD","D->A","B->E","E->B","BC->A"]),
("local","ABCDEF",["DF->C","ACE->D","AE->B","AF->D","BDE->A","DE->F"]),
("gap n=3","STZPQR",["ST->Z","Z->T","Z->PQR"]),
("antichain m=4","ABE1234",["B->A"]+[x for Y in itertools.combinations("1234",2) for x in ("B"+"".join(Y)+"->E","A"+"".join(Y)+"E->B")])]
for name,a,f in cases:
    N,F=parse(a,f)
    for mode in ("full","plain"):
        ref,_,_=solve(N,F,mode=mode)
        got,b,it=hitloop(N,F,mode=mode)
        print(f"{name:15s} {mode:5s} ref={ref} hit={got} iters={it} bounds={b}", "" if ref==got else "MISMATCH")
attrs="ABCDEF"; N,F=parse(attrs,["DF->C","ACE->D","AE->B","AF->D","BDE->A","DE->F"])
w=lambda f: 1 if show(attrs,f) in {"AE->B","AF->C","AF->D"} else 4
print("local weighted full", solve(N,F,w=w)[0], hitloop(N,F,w=w)[:1])
# random
rng=random.Random(7); mism=0; n=0; agg=[]
while n<400:
    N=rng.choice([5,6]); F=[]
    for _ in range(rng.randint(3,7)):
        L=0
        for _ in range(rng.choice([1,2,2,3])): L|=1<<rng.randrange(N)
        a=rng.randrange(N)
        if not (L>>a)&1: F.append((L,a))
    Sa=minimal_fds(N,table(N,F))
    if len(Sa)>16 or analyse(N,table(N,Sa))[0]: continue
    n+=1
    for mode in ("full","plain"):
        ref,_,_=solve(N,F,mode=mode); got,b,it=hitloop(N,F,mode=mode)
        if ref!=got: mism+=1; print("MISMATCH",N,F,mode,ref,got)
        if mode=="full": agg.append((it,b[0],ref))
print("random lossy instances:",n,"mismatches:",mism)
print("mean iterations:",sum(a[0] for a in agg)/len(agg),
      " first bound == optimum in",sum(a[1]==a[2] for a in agg),"of",len(agg))
