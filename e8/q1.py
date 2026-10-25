import sys, itertools, time; sys.path.insert(0, sys.argv[1])
from minloss import *
# R = A B E C1..Cm ; contexts Y = all floor(m/2)-subsets of {C1..Cm}
for m in (2,3,4):
    Cs=[f"{i}" for i in range(1,m+1)]
    attrs="ABE"+"".join(Cs)
    fds=["B->A"]
    for Y in itertools.combinations(Cs, m//2):
        y="".join(Y); fds+= ["B"+y+"->E","A"+y+"E->B"]
    N,S=parse(attrs,fds)
    t=time.time()
    full,sols,Sa=solve(N,S,mode="full")
    plain,_,_=solve(N,S,mode="plain")
    cl=table(N,Sa); ok,mins,unc,bad=analyse(N,cl)
    obs=[f for f in Sa if not (table(N,[u for u in unc])[f[0]]>>f[1])&1]
    D,g=sols[0]
    weak=[show(attrs,f) for f in g if f not in Sa]
    print(f"m={m} |R|={N} |Y|={len(fds)//2} |Sa|={len(Sa)} |O|={len(obs)} loss={full} plain={plain} "
          f"lost={[show(attrs,f) for f in D]} weakenings={weak} ({time.time()-t:.1f}s)")
