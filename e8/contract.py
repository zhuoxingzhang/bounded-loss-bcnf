"""Is enforceability (faithful BCNF) preserved under contraction and under restriction of a closed FD set?"""
import sys, random; sys.path.insert(0, sys.argv[1])
from minloss import *
def contract_table(N, cl, O):
    keep=[b for b in range(N) if not (O>>b)&1]; n=len(keep)
    out=[0]*(1<<n)
    for x in range(1<<n):
        X=sum(1<<keep[k] for k in range(n) if (x>>k)&1)
        c=cl[X|O]
        out[x]=sum(1<<k for k in range(n) if (c>>keep[k])&1)
    return n,out
def restrict_table(N, cl, O):
    keep=[b for b in range(N) if not (O>>b)&1]; n=len(keep)
    out=[0]*(1<<n)
    for x in range(1<<n):
        X=sum(1<<keep[k] for k in range(n) if (x>>k)&1)
        c=cl[X]
        out[x]=sum(1<<k for k in range(n) if (c>>keep[k])&1)
    return n,out
rng=random.Random(5); tried=0; cbad=0; rbad=0; ex=None
while tried<4000:
    N=rng.randint(4,7); F=[]
    for _ in range(rng.randint(2,7)):
        L=0
        for _ in range(rng.choice([1,2,2,3])): L|=1<<rng.randrange(N)
        a=rng.randrange(N)
        if not (L>>a)&1: F.append((L,a))
    cl=table(N,F)
    if not analyse(N,cl)[0]: continue
    O=rng.randrange(1,(1<<N)-1)
    tried+=1
    n,c=contract_table(N,cl,O)
    if not analyse(n,c)[0]:
        cbad+=1; ex=ex or (N,F,O)
    n,r=restrict_table(N,cl,O)
    if not analyse(n,r)[0]: rbad+=1
print("enforceable E tested",tried," contraction not enforceable:",cbad," restriction not enforceable:",rbad)
print("example",ex)
