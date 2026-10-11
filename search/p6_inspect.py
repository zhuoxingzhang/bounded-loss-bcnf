import sys, time, random
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))   # the oracle layer minloss_bruteforce.py and weak_stats.py lives in src/
from weak_stats import optimal_sets, random_instance
from minloss_bruteforce import *
n = 5; names = list("abcde"); rng = random.Random(77); t0 = time.time(); shown = 0
def inside(c1, c2): return all((c1[X] & ~c2[X]) == 0 for X in range(1 << n))
while time.time() - t0 < 60 and shown < 2:
    D = random_instance(n, rng); cltD = closure_table(D, n)
    if cltD[0] != 0: continue
    r = optimal_sets(n, D)
    if r is None: continue
    lam, Da, hits = r
    if lam == 0: continue
    byE = {tuple(clt): (Delta, clt) for Delta, clt in hits}
    if any(not [f for f in atomic_cover(clt, n) if f not in Da] for (_, clt) in byE.values()): continue
    info = {}
    for key, (Delta, clt) in byE.items():
        Psi = [f for f in Da if f not in Delta]; cltPsi = closure_table(Psi, n)
        crit = [(Y, B) for (Y, B) in atomic_cover(cltPsi, n) if not is_bcnf_schema(Y | B, cltPsi)]
        Ea = atomic_cover(clt, n); U = [f for f in Ea if is_bcnf_schema(f[0] | f[1], clt)]
        W_all = [f for f in Ea if f not in Da]
        comp = {f: any((f[0] & ~cltPsi[Y]) == 0 for (Y, B) in crit) for f in W_all}
        ok = closure_table(Psi + [f for f in W_all if comp[f]], n) == list(clt)
        info[key] = (Delta, Psi, cltPsi, crit, Ea, U, W_all, comp, ok, clt)
    bad = [k for k, v in info.items() if not v[8]]
    if not bad: continue
    k = bad[0]; Delta, Psi, cltPsi, crit, Ea, U, W_all, comp, ok, clt = info[k]
    smaller = [k2 for k2 in info if k2 != k and inside(k2, k)]
    print("D =", [fmt_fd(f, names) for f in D], " lambda =", lam)
    print(" Delta =", [fmt_fd(f, names) for f in Delta])
    print(" Psi-critical:", [(fmt_fd(f, names), fmt_set(cltPsi[f[0]], names)) for f in crit])
    print(" NON-MINIMAL E failing P6*: E_a =", [fmt_fd(f, names) for f in Ea])
    print("   uncritical:", [fmt_fd(f, names) for f in U])
    print("   weakenings:", [(fmt_fd(f, names), 'c' if comp[f] else 'NC', 'u' if f in U else 'crit') for f in W_all])
    for k2 in smaller:
        Delta2, Psi2, cltPsi2, crit2, Ea2, U2, W2, comp2, ok2, clt2 = info[k2]
        print(" smaller optimal E (P6* %s): E_a =" % ok2, [fmt_fd(f, names) for f in Ea2])
        print("   uncritical:", [fmt_fd(f, names) for f in U2])
        print("   weakenings:", [(fmt_fd(f, names), 'c' if comp2[f] else 'NC', 'u' if f in U2 else 'crit') for f in W2])
    print(); shown += 1
