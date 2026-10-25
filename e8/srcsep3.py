import sys, random; sys.path.insert(0, sys.argv[1])
from minloss import *
from multiprocessing import Pool
exec(open(sys.argv[1]+"/srcsep.py").read().split("def inst(")[0].split("from multiprocessing import Pool")[1])
# gadget on (a,b,e) with source contexts: b->a, b+Y->e, a+Y+e->b
def gadget(a,b,e,ctxs):
    F=[(1<<b,a)]
    for Y in ctxs:
        F+= [((1<<b)|Y,e), ((1<<a)|Y|(1<<e),b)]
    return F
def inst(seed):
    rng=random.Random(seed)
    ns=rng.choice([2,2,3]); src=list(range(ns))
    nparts=2
    parts=[]; F=[]; k=ns
    for _ in range(nparts):
        P=list(range(k,k+3)); k+=3; parts.append(P)
        ctx=rng.sample(src, rng.choice([2,min(3,ns)]))
        ctxs=[1<<c for c in ctx] if rng.random()<0.6 else [(1<<ctx[0])|(1<<ctx[1])] + [1<<c for c in ctx[2:]]
        if len(ctxs)<2: ctxs=[1<<ctx[0],1<<ctx[1]]
        F+=gadget(P[0],P[1],P[2],ctxs)
        for _ in range(rng.randint(0,2)):   # perturbation inside the part
            L=0
            for _ in range(rng.choice([1,2])): L|=1<<rng.choice(P+src)
            a=rng.choice(P)
            if not (L>>a)&1: F.append((L,a))
    N=k
    try:
        whole,_,_=solve(N,F,mode="full"); wp,_,_=solve(N,F,mode="plain")
        tot=0; totp=0
        for P in parts:
            n,Fi=restrict(F,src+P); tot+=solve(n,Fi,mode="full")[0]; totp+=solve(n,Fi,mode="plain")[0]
    except RuntimeError: return None
    return (seed,whole,tot,wp,totp)
if __name__=="__main__":
    with Pool(12) as p: out=[r for r in p.map(inst, range(1500)) if r]
    nonplain=[r for r in out if r[1]<r[3]]
    bad=[r for r in out if r[1]!=r[2]]; badp=[r for r in out if r[3]!=r[4]]
    print("instances",len(out),"needing weakenings",len(nonplain),"full mismatches",len(bad),bad[:5],"plain mismatches",len(badp))
