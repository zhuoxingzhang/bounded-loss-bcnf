"""Parts P1, P2 sharing only source attributes Src: is lambda(whole) = lambda(P1+Src) + lambda(P2+Src)?"""
import sys, random; sys.path.insert(0, sys.argv[1])
from minloss import *
from multiprocessing import Pool
def restrict(F, keep):  # FDs with lhs and rhs inside keep, re-indexed
    idx={a:i for i,a in enumerate(keep)}
    out=[]
    for L,a in F:
        if a in idx and all((L>>b)&1==0 or b in idx for b in range(16)):
            out.append((sum(1<<idx[b] for b in range(16) if (L>>b)&1), idx[a]))
    return len(keep), out
def inst(seed):
    rng=random.Random(seed)
    ns=rng.randint(1,2); n1=rng.randint(2,3); n2=rng.randint(2,3)
    src=list(range(ns)); P1=list(range(ns,ns+n1)); P2=list(range(ns+n1,ns+n1+n2)); N=ns+n1+n2
    F=[]
    for P in (P1,P2):
        for _ in range(rng.randint(2,5)):
            pool=P+src
            L=0
            for _ in range(rng.choice([1,2,2,3])): L|=1<<rng.choice(pool)
            a=rng.choice(P)
            if not (L>>a)&1: F.append((L,a))
    res={}
    for mode in ("full","plain"):
        try:
            w,_,_=solve(N,F,mode=mode)
            n,F1=restrict(F,src+P1); a,_,_=solve(n,F1,mode=mode)
            n,F2=restrict(F,src+P2); b,_,_=solve(n,F2,mode=mode)
        except RuntimeError: return None
        res[mode]=(w,a+b)
    return seed,N,F,res
if __name__=="__main__":
    with Pool(12) as p: out=[r for r in p.map(inst, range(3000)) if r]
    tot=len(out); lossy=sum(1 for r in out if r[3]["full"][0]>0)
    bad={m:[r for r in out if r[3][m][0]!=r[3][m][1]] for m in ("full","plain")}
    print("instances",tot,"with positive loss",lossy)
    for m in bad: print(m,"mismatches",len(bad[m]), [ (r[0],r[3][m]) for r in bad[m][:5]])
