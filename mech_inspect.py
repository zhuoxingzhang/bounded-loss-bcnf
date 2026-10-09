import sys, time, random
from weak_stats import random_instance
from minloss_bruteforce import *
n = 5; names = list("abcde"); rng = random.Random(131); t0 = time.time(); shown = 0
def inside(c1, c2): return all((c1[X] & ~c2[X]) == 0 for X in range(1 << n))
while time.time() - t0 < 100 and shown < 4:
    D = random_instance(n, rng); cltD = closure_table(D, n)
    if cltD[0] != 0 or realizable(cltD, n): continue
    Da = atomic_cover(cltD, n); FD = closed_sets(cltD, n)
    byPsi = {}
    for F in coarser_families(FD, n):
        clt = family_to_closure_table(F, n)
        if realizable(clt, n):
            byPsi.setdefault(frozenset(f for f in Da if clt[f[0]] & f[1]), []).append(clt)
    for Psi, Es in byPsi.items():
        cltPsi = closure_table(list(Psi), n)
        if any(list(clt) == cltPsi for clt in Es): continue
        crit = [Y for (Y, B) in atomic_cover(cltPsi, n) if not is_bcnf_schema(Y | B, cltPsi)]
        for clt in Es:
            Ea = atomic_cover(clt, n)
            W_c = [f for f in Ea if f not in Da and any((f[0] & ~cltPsi[Y]) == 0 for Y in crit)]
            cltEc = closure_table(list(Psi) + W_c, n)
            if cltEc == list(clt) or realizable(cltEc, n): continue
            # bad pair with lambda > 0
            sup = [P2 for P2 in byPsi if P2 > Psi]
            maxsup = [P2 for P2 in sup if not any(P3 > P2 for P3 in sup)]
            print(f"D={[fmt_fd(f, names) for f in D]}  Psi={sorted(fmt_fd(f, names) for f in Psi)}  crit={[fmt_set(Y, names)+':'+fmt_set(cltPsi[Y], names) for Y in crit]}")
            print(f"  E_a={[fmt_fd(f, names) for f in Ea]}  W_c={[fmt_fd(f, names) for f in W_c]}  nonlocal={[fmt_fd(f, names) for f in Ea if f not in Da and f not in W_c]}")
            for P2 in maxsup:
                for clt2 in byPsi[P2]:
                    rel = ('E2 contains E' if inside(clt, clt2) else '') + (' E2 contains E_c' if inside(cltEc, clt2) else '') + (' E2 inside E' if inside(clt2, clt) else '')
                    Ea2 = atomic_cover(clt2, n)
                    print(f"  feasible Psi'={sorted(fmt_fd(f, names) for f in P2)}  E'_a={[fmt_fd(f, names) for f in Ea2]}  [{rel}]")
            print(); shown += 1
            break
        if shown >= 4: break
