import sys, random; sys.path.insert(0, sys.argv[1])
from minloss import *
exec(open(sys.argv[1]+"/contract.py").read().split("rng=random.Random(5)")[0].split("from minloss import *")[1])
rng=random.Random(9); tried=0; stats={"contr":0,"restr":0,"cross":0}; ex={}
while tried<3000:
    ns=rng.randint(1,2); n1=rng.randint(2,3); n2=rng.randint(1,3)
    src=list(range(ns)); P1=list(range(ns,ns+n1)); P2=list(range(ns+n1,ns+n1+n2)); N=ns+n1+n2
    F=[]
    for P in (P1,P2):
        for _ in range(rng.randint(2,5)):
            L=0
            for _ in range(rng.choice([1,2,2,3])): L|=1<<rng.choice(P+src)
            a=rng.choice(P)
            if not (L>>a)&1: F.append((L,a))
    clS=table(N,F); Sa=minimal_fds(N,clS)
    if not Sa: continue
    # random E within Sigma^+: random subset of Sa plus random weakenings (possibly crossing parts)
    G=[f for f in Sa if rng.random()<0.7]
    for _ in range(rng.randint(0,4)):
        X,a=rng.choice(Sa); Xp=X
        for _ in range(rng.randint(1,2)): Xp|=1<<rng.randrange(N)
        if not (Xp>>a)&1: G.append((Xp,a))
    cl=table(N,G)
    if not analyse(N,cl)[0]: continue
    tried+=1
    O=sum(1<<b for b in P2)
    crossing=any(((X & O) and (a in P1)) or ((X & sum(1<<b for b in P1)) and a in P2) for X,a in minimal_fds(N,cl))
    stats["cross"]+=crossing
    n,c=contract_table(N,cl,O)
    if not analyse(n,c)[0]: stats["contr"]+=1; ex.setdefault("contr",(N,src,P1,P2,G))
    n,r=restrict_table(N,cl,O)
    if not analyse(n,r)[0]: stats["restr"]+=1; ex.setdefault("restr",(N,src,P1,P2,G))
print("structured enforceable E:",tried,"with crossing minimal FDs:",stats["cross"])
print("contraction fails:",stats["contr"]," restriction fails:",stats["restr"])
print(ex)
