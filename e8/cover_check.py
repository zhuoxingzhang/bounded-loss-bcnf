import sys, random; sys.path.insert(0, sys.argv[1])
from minloss import *
sys.argv=[sys.argv[0],sys.argv[1]]
exec(open(sys.argv[1]+"/conp_check.py").read().split("def sat(")[0].split("from minloss import *")[1])
def expected(n,clauses,ix):
    m_=lambda *xs: sum(1<<ix[x] for x in xs)
    L=[f"P{i}" for i in range(n)]+[f"Q{i}" for i in range(n)]; C=[f"C{j}" for j in range(len(clauses))]
    E={(m_(*L,"Z"),ix["T"]),(m_(*L,*C),ix["T"]),(m_("T"),ix["Z"]),(m_(*C),ix["Z"])}
    for j,c in enumerate(clauses):
        for l in c: E.add((m_("T","P%d"%(l-1) if l>0 else "Q%d"%(-l-1)),ix[f"C{j}"]))
        vars_=set(abs(l)-1 for l in c)
        for i in range(n):
            if i not in vars_: E.add((m_(f"P{i}",f"Q{i}","T"),ix[f"C{j}"]))
        E.add((m_(*L,"Z"),ix[f"C{j}"]))
    for i in range(n):
        for b in L:
            if b not in (f"P{i}",f"Q{i}"): E.add((m_(f"P{i}",f"Q{i}","T"),ix[b]))
    return E
rng=random.Random(11); bad=0; cnt=0
for _ in range(60):
    n=rng.randint(1,3); m=rng.randint(1,3)
    cl=[[rng.choice([1,-1])*rng.randint(1,n) for _ in range(rng.randint(1,3))] for _ in range(m)]
    N,F,attrs,ix=build(n,cl)
    if N>11: continue
    Sa=set(minimal_fds(N,table(N,F))); cnt+=1
    if Sa!=expected(n,cl,ix): bad+=1; print("DIFF",n,cl)
print("instances",cnt,"mismatches",bad)
