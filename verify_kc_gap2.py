import sys
from sample_kc import *
names = ['a','b','c','d','e']
idx = {c:i for i,c in enumerate(names)}
def fd(s):
    l, r = s.split('->')
    return (sum(1 << idx[c] for c in l), sum(1 << idx[c] for c in r))
D = [fd(s) for s in ['b->e','ce->a','ce->b','ade->b','abd->c']]
n = 5
cltD = closure_table(D, n)
Da = atomic_cover(cltD, n)
print("D_a =", [fmt_fd(f, names) for f in Da])
print("minimal keys of R:", [fmt_set(K, names) for K in minimal_keys_of(31, cltD)])
fams = coarser_families(closed_sets(cltD, n), n)
print("coarser families:", len(fams))
best = None; opt = []; plain_best = None; kc_best = None
for F in fams:
    clt = family_to_closure_table(F, n)
    if not realizable(clt, n):
        continue
    loss = sum(1 for f in Da if not (clt[f[0]] & f[1]))
    if best is None or loss < best:
        best = loss; opt = []
    if loss == best:
        opt.append(clt)
    if is_plain(clt, Da, n) and (plain_best is None or loss < plain_best): plain_best = loss
    if kc_feasible(clt, cltD, n) and (kc_best is None or loss < kc_best): kc_best = loss
print("lambda =", best, "plain =", plain_best, "kc (closure-system test) =", kc_best, " #optimal enforceable E:", len(opt))
for clt in opt:
    Ea = atomic_cover(clt, n)
    unc = [f for f in Ea if is_bcnf_schema(f[0] | f[1], clt)]
    print("  E_a =", [fmt_fd(f, names) for f in Ea], " plain:", is_plain(clt, Da, n), " kc:", kc_feasible(clt, cltD, n))
    print("     uncritical:", [fmt_fd(f, names) for f in unc])
    print("     dropped:", [fmt_fd(f, names) for f in Da if not (clt[f[0]] & f[1])])
    print("     E-minimal keys of R:", [fmt_set(K, names) for K in minimal_keys_of(31, clt)])
ms = int(sys.argv[1]) if len(sys.argv) > 1 else 5
lam_kc, des = key_complete_designs(n, D, max_schemas=ms, verbose=False)
print("cross-check key_complete_designs(max_schemas=%d): lambda_kc =" % ms, lam_kc, " design:", None if des is None else ([fmt_set(S, names) for S in des[0]], [fmt_fd(f, names) for f in des[1]]))
