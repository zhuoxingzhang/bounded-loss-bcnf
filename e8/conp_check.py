"""Reduction: CNF phi -> (R, Sigma_a, Delta={T->Z}); Delta realizable iff phi unsatisfiable."""
import sys, itertools, random; sys.path.insert(0, sys.argv[1])
from minloss import *
def build(n, clauses):
    # attributes: P_i (x_i), Q_i (not x_i), C_j, T, Z
    attrs=[f"P{i}" for i in range(n)]+[f"Q{i}" for i in range(n)]+[f"C{j}" for j in range(len(clauses))]+["T","Z"]
    ix={a:k for k,a in enumerate(attrs)}; m=lambda *xs: sum(1<<ix[x] for x in xs)
    F=[]
    lits=[f"P{i}" for i in range(n)]+[f"Q{i}" for i in range(n)]
    X=m(*lits,"Z"); F.append((X,ix["T"]))                       # f: P..Q..Z -> T
    for i in range(n):
        for a in lits+["Z"]: F.append((m(f"P{i}",f"Q{i}","T"),ix[a]))   # k_i
    for j,c in enumerate(clauses):
        for l in c: F.append((m("T", f"P{l-1}" if l>0 else f"Q{-l-1}"), ix[f"C{j}"]))
    F.append((m(*[f"C{j}" for j in range(len(clauses))]),ix["Z"]))
    F.append((m("T"),ix["Z"]))                                   # shortcut, Delta
    return len(attrs),F,attrs,ix
def sat(n,clauses):
    return any(all(any((l>0)==bool(v[abs(l)-1]) for l in c) for c in clauses) for v in itertools.product([0,1],repeat=n))
def check(n,clauses):
    N,F,attrs,ix=build(n,clauses)
    Sa=minimal_fds(N,table(N,F))
    Delta=[(1<<ix["T"],ix["Z"])]; assert Delta[0] in Sa
    Psi=[f for f in Sa if f not in Delta]
    clP=table(N,Psi); assert not hits(clP,Delta)
    plain=analyse(N,clP)[0]
    full=complete_full(N,Psi,Delta) is not None
    s=sat(n,clauses)
    ok = (plain==(not s)) and (full==(not s))
    print(f"n={n} m={len(clauses)} |R|={N} |Sa|={len(Sa)} sat={s} plain_realizable={plain} full_realizable={full}", "OK" if ok else "FAIL", flush=True)
    return ok
tests=[(1,[[1],[-1]]),(1,[[1]]),(2,[[1,2],[-1,2],[1,-2],[-1,-2]]),(2,[[1,2],[-1,-2]]),(2,[[1],[-1,2],[-2]]),
       (2,[[1,-2],[2]]),(3,[[1,2],[-1,3],[-2,-3]]),(2,[[1],[-1,2],[-2],[2]])]
rng=random.Random(3)
for _ in range(12):
    n=rng.randint(1,3); m=rng.randint(2,4)
    if 2*n+m+2>10: m=10-2-2*n
    tests.append((n,[[rng.choice([1,-1])*rng.randint(1,n) for _ in range(rng.randint(1,2))] for _ in range(m)]))
print(all([check(n,c) for n,c in tests]))
