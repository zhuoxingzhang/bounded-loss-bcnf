import sys, time
from minloss_bruteforce import *
from weak_stats import optimal_sets
def m(t): return sum(1 << (ord(c) - 97) for c in t)
def fd(s):
    l, r = s.split('->'); return (m(l), m(r))
base = ['bcd->f', 'cdf->b', 'c->d', 'bde->f', 'a->b', 'cef->a']
variants = {
 'V1 n7 +ac->g,g->f': (7, base + ['ac->g', 'g->f']),
 'V3 n7 +cef->g,g->a': (7, base + ['cef->g', 'g->a']),
 'V5 n7 +bc->g,g->f': (7, base + ['bc->g', 'g->f']),
 'V6 n7 +a->g,g->b': (7, base + ['a->g', 'g->b']),
 'V2 n8 +ac->g,g->f,bc->h,h->f': (8, base + ['ac->g', 'g->f', 'bc->h', 'h->f']),
 'V4 n8 +ac->g,g->f,cef->h,h->a': (8, base + ['ac->g', 'g->f', 'cef->h', 'h->a']),
}
for name, (n, fds) in variants.items():
    names = [chr(97 + i) for i in range(n)]
    D = [fd(s) for s in fds]
    t0 = time.time()
    r = optimal_sets(n, D, cap=400000)
    if r is None:
        print(name, ": cap exceeded"); continue
    lam, Da, hits = r
    verdicts = []
    for Delta, clt in hits:
        Psi = [f for f in Da if f not in Delta]; cltPsi = closure_table(Psi, n)
        crit = [Y for (Y, B) in atomic_cover(cltPsi, n) if not is_bcnf_schema(Y | B, cltPsi)]
        Ea = atomic_cover(clt, n); W = [f for f in Ea if f not in Da]
        Wc = [f for f in W if any((f[0] & ~cltPsi[Y]) == 0 for Y in crit)]
        ok = closure_table(Psi + Wc, n) == list(clt)
        verdicts.append((tuple(sorted(fmt_fd(f, names) for f in Delta)), ok))
    byD = {}
    for d, ok in verdicts:
        byD[d] = byD.get(d, False) or ok
    print(f"{name}: lambda={lam} |D_a|={len(Da)} t={time.time()-t0:.0f}s  optimal Deltas: " + "; ".join(f"{list(d)} {'LOCAL' if ok else 'NONLOCAL'}" for d, ok in byD.items()), flush=True)
