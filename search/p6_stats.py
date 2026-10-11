r"""Variants of property P6 (weakening LHS inside the Psi-closure of a Psi-critical LHS) on optimal designs.

For each optimal enforceable E (same minimum loss) with Delta, Psi = D_a cap E:
  gens  = inclusion-minimal generating sets W' (size <= 4) of E from Psi and uncritical weakenings.
  P6(W') = every X'->A in W' has X' inside Y+_Psi for some Psi-critical minimal FD Y->B of Psi^+.
Aggregates per instance:
  any_pair : some (E, W') satisfies P6                     (what weak_stats reports)
  all_E    : every optimal E has some W' satisfying P6
  all_pair : every (E, W') satisfies P6
  min_E    : every inclusion-minimal optimal E (no optimal E' strictly inside) has some W' satisfying P6
  one_Y    : some (E, W') has a single Psi-critical Y whose closure contains every LHS of W'
"""
import sys, time, random
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))   # the oracle layer minloss_bruteforce.py and weak_stats.py lives in src/
from weak_stats import optimal_sets, generating_sets, random_instance
from minloss_bruteforce import *

def main(n, seconds, cap, seed):
    rng = random.Random(seed)
    names = [chr(ord('a') + i) for i in range(n)]
    t0 = time.time(); seen = set()
    stats = {'instances': 0, 'nonplain': 0, 'any_pair_fail': 0, 'all_E_fail': 0, 'all_pair_fail': 0, 'min_E_fail': 0, 'one_Y_fail': 0, 'nogen': 0}
    while time.time() - t0 < seconds:
        D = random_instance(n, rng)
        cltD = closure_table(D, n)
        if cltD[0] != 0:
            continue
        sig = tuple(cltD)
        if sig in seen:
            continue
        seen.add(sig)
        r = optimal_sets(n, D, cap=cap)
        if r is None:
            continue
        lam, Da, hits = r
        stats['instances'] += 1
        if lam == 0:
            continue
        # keep one entry per distinct E
        byE = {}
        for Delta, clt in hits:
            byE[tuple(clt)] = (Delta, clt)
        Es = list(byE.values())
        if any(all(f for f in [1]) and not [f for f in atomic_cover(clt, n) if f not in Da] for (_, clt) in Es):
            continue  # some optimal E is plain: property holds trivially with W' = {}
        stats['nonplain'] += 1
        perE = {}
        for Delta, clt in Es:
            Psi = [f for f in Da if f not in Delta]
            cltPsi = closure_table(Psi, n)
            PsiA = atomic_cover(cltPsi, n)
            crit = [Y for (Y, B) in PsiA if not is_bcnf_schema(Y | B, cltPsi)]
            Ea = atomic_cover(clt, n)
            U = [f for f in Ea if is_bcnf_schema(f[0] | f[1], clt)]
            W_unc = [f for f in U if f not in Da]
            gens = generating_sets(Psi, W_unc, clt, n)
            if not gens:
                stats['nogen'] += 1
            res = []
            for Wp in gens:
                ok = all(any((Xp & ~cltPsi[Y]) == 0 for Y in crit) for (Xp, A) in Wp)
                oneY = any(all((Xp & ~cltPsi[Y]) == 0 for (Xp, A) in Wp) for Y in crit) or not Wp
                res.append((ok, oneY))
            perE[tuple(clt)] = (res, Delta, clt)
        any_pair = any(ok for (res, _, _) in perE.values() for (ok, _) in res)
        all_E = all(any(ok for (ok, _) in res) for (res, _, _) in perE.values() if res)
        all_pair = all(ok for (res, _, _) in perE.values() for (ok, _) in res)
        one_Y = any(oy for (res, _, _) in perE.values() for (_, oy) in res)
        # inclusion-minimal optimal E: closed-set family larger (coarser) => E smaller; E1 inside E2 iff clt1[X] subset clt2[X] for all X
        keys = list(perE.keys())
        def inside(c1, c2):
            return all((c1[X] & ~c2[X]) == 0 for X in range(1 << n))
        minimal = [k for k in keys if not any(k2 != k and inside(k2, k) for k2 in keys)]
        min_E = all(any(ok for (ok, _) in perE[k][0]) for k in minimal if perE[k][0])
        for name, ok in [('any_pair', any_pair), ('all_E', all_E), ('all_pair', all_pair), ('min_E', min_E), ('one_Y', one_Y)]:
            if not ok:
                stats[name + '_fail'] += 1
                if name in ('any_pair', 'min_E'):
                    print(f"FAIL {name}: lambda={lam} D={[fmt_fd(f, names) for f in D]}", flush=True)
        if stats['instances'] % 5000 == 0:
            print(f"  ... {time.time()-t0:.0f}s {stats}", flush=True)
    print("DONE", stats, f"{time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 200000
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 31
    main(n, seconds, cap, seed)
