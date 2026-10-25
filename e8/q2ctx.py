import sys, itertools, time; sys.path.insert(0, sys.argv[1])
from minloss import *
from multiprocessing import Pool
base=["DF->C","ACE->D","AE->B","AF->D","BDE->A","DE->F"]
nctx=int(sys.argv[2])
ctx="GHIJ"[:nctx]
attrs="ABCDEF"+ctx
def job(mask):
    fds=[]
    for j,f in enumerate(base):
        l,r=f.split("->")
        if (mask>>j)&1: fds+=[l+c+"->"+r for c in ctx]
        else: fds.append(f)
    N,F=parse(attrs,fds)
    Sa=minimal_fds(N,table(N,F))
    try:
        full,sols,_=solve(N,F,mode="full",maxk=6)
        plain,_,_=solve(N,F,mode="plain",maxk=8)
        loc,_,_=solve(N,F,mode="local",maxk=8) if full is not None and plain!=full else (plain,None,None)
    except RuntimeError: return (mask,len(Sa),"limit")
    return (mask,len(Sa),full,plain,loc,[show(attrs,f) for f in sols[0][0]] if sols else None)
if __name__=="__main__":
    with Pool(2) as p:
        for r in p.imap_unordered(job, range(64)):
            m=r[0]; flag = "  <== local>full" if len(r)>4 and r[2] is not None and r[4]!=r[2] else ""
            print([base[j] for j in range(6) if (m>>j)&1], r[1:], flag, flush=True)
