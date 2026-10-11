r"""Fast test of the weighted local-weakening theorem (candidate) and of the un-drop mechanism.
For each instance: enumerate all closed choices Delta (subsets of D_a whose complement implies nothing in Delta),
compute F(Psi) by families_between + realizable (cap), record feasible Delta's.
Inclusion-minimal feasible Delta = feasible with no feasible proper subset.
Per (Delta, E) with E in F(Psi), non-plain: E_c = (Psi cup local minimal weakenings)^+.
  T1: Delta inclusion-minimal feasible  =>  E_c enforceable for EVERY E in F(Psi)         (strong theorem candidate)
  T2: Delta inclusion-minimal feasible  =>  some E in F(Psi) is locally generated         (what Drop needs)
Bad pairs (E_c not enforceable) only at non-minimal Delta if T1 holds; for them, test which un-drop repairs:
  U_any: some single X->A in Delta with (E cup {X->A})^+ enforceable
  U_loc: some such X->A with X local (X inside some critical closure)
  U_all_loc: (E cup Delta_loc)^+ enforceable, Delta_loc = dropped FDs with local LHS
"""
import sys, time, random
from itertools import combinations
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))   # the oracle layer minloss_bruteforce.py and weak_stats.py lives in src/
from weak_stats import families_between, random_instance
from minloss_bruteforce import *

def main(n, seconds, cap, seed):
    rng = random.Random(seed)
    names = [chr(ord('a') + i) for i in range(n)]
    t0 = time.time(); seen = set()
    stats = {'instances': 0, 'skipped': 0, 'min_Delta': 0, 'min_Delta_nonplain': 0, 'T1_fail': 0, 'T2_fail': 0,
             'bad_pairs': 0, 'U_any_fail': 0, 'U_loc_fail': 0, 'U_all_loc_fail': 0, 'bad_Delta_loc_empty': 0}
    while time.time() - t0 < seconds:
        D = random_instance(n, rng)
        cltD = closure_table(D, n)
        if cltD[0] != 0:
            continue
        sig = tuple(cltD)
        if sig in seen:
            continue
        seen.add(sig)
        Da = atomic_cover(cltD, n)
        FD = closed_sets(cltD, n)
        feasible = {}  # frozenset(Delta) -> list of clt
        skip = False
        for k in range(0, len(Da) + 1):
            for Delta in combinations(Da, k):
                Psi = [f for f in Da if f not in Delta]
                cltPsi = closure_table(Psi, n)
                if any(cltPsi[X] & A for (X, A) in Delta):
                    continue
                FPsi = closed_sets(cltPsi, n)
                fams = families_between(FD, FPsi, n)
                if len(fams) > cap:
                    skip = True; break
                Es = []
                for F in fams:
                    clt = family_to_closure_table(F, n)
                    if sum(1 for (X, A) in Da if not (clt[X] & A)) != k:
                        continue
                    if realizable(clt, n):
                        Es.append(clt)
                if Es:
                    feasible[frozenset(Delta)] = Es
            if skip:
                break
        if skip:
            stats['skipped'] += 1; continue
        stats['instances'] += 1
        for Delta, Es in feasible.items():
            Psi = [f for f in Da if f not in Delta]
            cltPsi = closure_table(Psi, n)
            if any(list(clt) == cltPsi for clt in Es):
                continue  # plain optimum exists for this Delta
            is_min = not any(D2 < Delta for D2 in feasible)
            crit = [Y for (Y, B) in atomic_cover(cltPsi, n) if not is_bcnf_schema(Y | B, cltPsi)]
            if is_min:
                stats['min_Delta'] += 1; stats['min_Delta_nonplain'] += 1
            t2 = False; t1 = True
            for clt in Es:
                Ea = atomic_cover(clt, n)
                W_c = [f for f in Ea if f not in Da and any((f[0] & ~cltPsi[Y]) == 0 for Y in crit)]
                cltEc = closure_table(Psi + W_c, n)
                if cltEc == list(clt):
                    t2 = True
                if realizable(cltEc, n):
                    continue
                t1 = False
                # bad pair: test un-drops
                stats['bad_pairs'] += 1
                Dl = [f for f in Delta if any((f[0] & ~cltPsi[Y]) == 0 for Y in crit)]
                if not Dl:
                    stats['bad_Delta_loc_empty'] += 1
                base = [(X, clt[X]) for X in range(1 << n)]
                u_any = u_loc = False
                for f in Delta:
                    if realizable(closure_table(base + [f], n), n):
                        u_any = True
                        if f in Dl:
                            u_loc = True
                u_all_loc = bool(Dl) and realizable(closure_table(base + Dl, n), n)
                if not u_any: stats['U_any_fail'] += 1
                if not u_loc: stats['U_loc_fail'] += 1
                if not u_all_loc: stats['U_all_loc_fail'] += 1
                if is_min or not u_any:
                    print(f"{'T1-FAIL' if is_min else 'UNDROP-FAIL'}: D={[fmt_fd(f, names) for f in D]} Delta={sorted(fmt_fd(f, names) for f in Delta)} crit={[fmt_set(Y, names) for Y in crit]} E_a={[fmt_fd(f, names) for f in Ea]} W_c={[fmt_fd(f, names) for f in W_c]}", flush=True)
            if is_min and not t1: stats['T1_fail'] += 1
            if is_min and not t2:
                stats['T2_fail'] += 1
                print(f"T2-FAIL: D={[fmt_fd(f, names) for f in D]} Delta={sorted(fmt_fd(f, names) for f in Delta)}", flush=True)
        if stats['instances'] % 200 == 0:
            print(f"  ... {time.time()-t0:.0f}s {stats}", flush=True)
    print("DONE", stats, f"{time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 240
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 100000
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 111
    main(n, seconds, cap, seed)
