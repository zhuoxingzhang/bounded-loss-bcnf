import sys
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))   # the oracle layer minloss_bruteforce.py and weak_stats.py lives in src/
from sample_kc import *
names = ['a','b','c','d','e']
idx = {c:i for i,c in enumerate(names)}
def fd(s):
    l, r = s.split('->')
    X = sum(1 << idx[c] for c in l); A = sum(1 << idx[c] for c in r)
    return (X, A)
D = [fd(s) for s in ['b->a','e->a','acd->b','bc->d','ad->e']]
n = 5
cltD = closure_table(D, n)
Da = atomic_cover(cltD, n)
print("D_a =", [fmt_fd(f, names) for f in Da])
print("minimal keys of R:", [fmt_set(K, names) for K in minimal_keys_of(31, cltD)])
FD = closed_sets(cltD, n)
fams = coarser_families(FD, n)
print("coarser families:", len(fams))
opt = []
best = None
for F in fams:
    clt = family_to_closure_table(F, n)
    if not realizable(clt, n):
        continue
    loss = sum(1 for f in Da if not (clt[f[0]] & f[1]))
    if best is None or loss < best:
        best = loss; opt = []
    if loss == best:
        opt.append(clt)
print("lambda =", best, " #optimal enforceable E:", len(opt))
for clt in opt:
    Ea = atomic_cover(clt, n)
    unc = [f for f in Ea if is_bcnf_schema(f[0] | f[1], clt)]
    print("  E_a =", [fmt_fd(f, names) for f in Ea], " plain:", is_plain(clt, Da, n), " kc:", kc_feasible(clt, cltD, n))
    print("     uncritical:", [fmt_fd(f, names) for f in unc])
    # details of G(E)
    G = []; keyfds = []
    for S in range(1, 1 << n):
        if not is_bcnf_schema(S, clt): continue
        kE = minimal_keys_of(S, clt); kD = minimal_keys_of(S, cltD)
        if set(kE) != set(kD): continue
        G.append(S)
        for K in kD:
            if K != S: keyfds.append((K, S))
    clK = closure_table(keyfds, n)
    missing = [fmt_fd(f, names) for f in Ea if not (clK[f[0]] & f[1])]
    print("     G(E) =", [fmt_set(S, names) for S in G if any((S & ~T) == 0 and S != T for T in G) is False])
    print("     key FDs of G(E) generate E?", clK == clt, " missing:", missing, " lossless:", lossless(G, keyfds, n) if G else None)
print("plain min:", min(sum(1 for f in Da if not (family_to_closure_table(F, n)[f[0]] & f[1])) for F in fams if realizable(family_to_closure_table(F, n), n) and is_plain(family_to_closure_table(F, n), Da, n)))
ms = int(sys.argv[1]) if len(sys.argv) > 1 else 5
print("independent cross-check: key_complete_designs with max_schemas =", ms)
lam_kc, des = key_complete_designs(n, D, max_schemas=ms, verbose=False)
print("lambda_kc =", lam_kc, " design:", None if des is None else ([fmt_set(S, names) for S in des[0]], [fmt_fd(f, names) for f in des[1]]))
