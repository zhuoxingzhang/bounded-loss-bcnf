import sys, random; sys.path.insert(0, sys.argv[1])
from minloss import *
from multiprocessing import Pool
exec(open(sys.argv[1]+"/srcsep.py").read().split("def inst(")[0].split("from multiprocessing import Pool")[1])
def inst(seed):
    rng=random.Random(seed)
    ns=rng.randint(1,2); sizes=[rng.randint(2,3) for _ in range(rng.choice([2,3]))]
    src=list(range(ns)); parts=[]; k=ns
    for s in sizes: parts.append(list(range(k,k+s))); k+=s
    N=k
    if N>9: return None
    F=[]
    for P in parts:
        for _ in range(rng.randint(2,5)):
            L=0
            for _ in range(rng.choice([1,2,2,3])): L|=1<<rng.choice(P+src)
            a=rng.choice(P)
            if not (L>>a)&1: F.append((L,a))
    try:
        whole,_,_=solve(N,F,mode="full"); wp,_,_=solve(N,F,mode="plain")
        if whole==0: return (seed,0,0,0,False)
        tot=0
        for P in parts:
            n,Fi=restrict(F,src+P); v,_,_=solve(n,Fi,mode="full"); tot+=v
    except RuntimeError: return None
    return (seed,whole,tot,wp,whole<wp)
if __name__=="__main__":
    with Pool(12) as p: out=[r for r in p.map(inst, range(6000)) if r]
    lossy=[r for r in out if r[1]>0]; nonplain=[r for r in lossy if r[4]]
    bad=[r for r in lossy if r[1]!=r[2]]
    print("instances",len(out),"lossy",len(lossy),"needing weakenings",len(nonplain),"mismatches",len(bad),bad[:5])
