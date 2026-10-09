r"""Stronger forms of the (now proved) hitting lemma, tested by brute force on random instances.

G(D): generators and violators of D-critical schemata (see cand_stats.candidate_sets).
H1: for EVERY enforceable closed E inside D^+ (not only optimal ones), D_a - E intersects G(D), provided lambda(R,D) > 0.
H2 (per-schema form): for every optimal E and every D-critical schema XA, D_a - E contains X->A or a violator of XA.
H3 (per-schema form for every enforceable E): as H2 for every enforceable E.
"""
import sys, time, random
from weak_stats import random_instance
from minloss_bruteforce import *
from cand_stats import candidate_sets

def critical_groups(n, D):
    cltD = closure_table(D, n)
    Da = atomic_cover(cltD, n)
    groups = []
    for (X, A) in Da:
        S = X | A
        if is_bcnf_schema(S, cltD):
            continue
        viol = [(Y, B) for (Y, B) in Da if not ((Y | B) & ~S) and (cltD[Y] & S) != S]
        groups.append(((X, A), viol))
    return Da, groups

def main(n, seconds, seed):
    rng = random.Random(seed)
    names = [chr(ord('a') + i) for i in range(n)]
    t0 = time.time(); seen = set()
    stats = {'instances': 0, 'nontrivial': 0, 'H1_fail': 0, 'H2_fail': 0, 'H3_fail': 0, 'enforceable_sets': 0}
    while time.time() - t0 < seconds:
        D = random_instance(n, rng)
        cltD = closure_table(D, n)
        if cltD[0] != 0:
            continue
        sig = tuple(cltD)
        if sig in seen:
            continue
        seen.add(sig)
        stats['instances'] += 1
        if realizable(cltD, n):
            continue
        stats['nontrivial'] += 1
        Da, G, _ = candidate_sets(n, D)
        _, groups = critical_groups(n, D)
        FD = closed_sets(cltD, n)
        best = None; sets = []
        for F in coarser_families(FD, n):
            clt = family_to_closure_table(F, n)
            if not realizable(clt, n):
                continue
            Delta = frozenset((X, A) for (X, A) in Da if not (clt[X] & A))
            sets.append(Delta)
            if best is None or len(Delta) < best:
                best = len(Delta)
        stats['enforceable_sets'] += len(sets)
        h1 = all(Delta & G for Delta in sets)
        def per_schema(Delta):
            return all(((X, A) in Delta) or any(v in Delta for v in viol) for ((X, A), viol) in groups)
        h3 = all(per_schema(Delta) for Delta in sets)
        h2 = all(per_schema(Delta) for Delta in sets if len(Delta) == best)
        for name, ok in [('H1', h1), ('H2', h2), ('H3', h3)]:
            if not ok:
                stats[name + '_fail'] += 1
                bad = [sorted(fmt_fd(f, names) for f in Delta) for Delta in sets if (name == 'H1' and not (Delta & G)) or (name != 'H1' and not per_schema(Delta) and (name == 'H3' or len(Delta) == best))]
                print(f"FAIL {name}: lambda={best} D={[fmt_fd(f, names) for f in D]} groups={[(fmt_fd(g, names), [fmt_fd(v, names) for v in viol]) for (g, viol) in groups]} bad={bad[:3]}", flush=True)
        if stats['instances'] % 500 == 0:
            print(f"  ... {time.time()-t0:.0f}s {stats}", flush=True)
    print("DONE", stats, f"{time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 9
    main(n, seconds, seed)
