r"""Test of the candidate lemma: is there always an optimal design whose unenforced minimal FDs are
generators or violators of critical schemata of D?

G(D) = { X->A in D_a : (XA, D[XA]) not in BCNF }                      (generators of critical schemata)
     cup { Y->B in D_a : exists critical XA with YB subset of XA and Y not a D-key of XA }   (violators)
Weaker variant G2: additionally FDs Y->B that are non-key FDs of SOME schema XA, X->A in D_a (critical or not).
Property C1: some optimal E has Delta(E) subset of G(D).
Property C2: some optimal E has Delta(E) subset of G2(D).
"""
import sys, time, random
from weak_stats import optimal_sets, random_instance
from minloss_bruteforce import *

def candidate_sets(n, D):
    cltD = closure_table(D, n)
    Da = atomic_cover(cltD, n)
    crit = [(X, A) for (X, A) in Da if not is_bcnf_schema(X | A, cltD)]
    G = set(crit); G2 = set(crit)
    for (X, A) in Da:
        S = X | A
        for (Y, B) in Da:
            if (Y | B) & ~S:
                continue
            if (cltD[Y] & S) == S:
                continue  # Y is a key of S
            G2.add((Y, B))
            if (X, A) in crit:
                G.add((Y, B))
    return Da, G, G2

def main(n, seconds, cap, seed):
    rng = random.Random(seed)
    names = [chr(ord('a') + i) for i in range(n)]
    t0 = time.time(); seen = set()
    stats = {'instances': 0, 'nontrivial': 0, 'C1_fail': 0, 'C2_fail': 0, 'skipped': 0}
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
            stats['skipped'] += 1; continue
        lam, Da, hits = r
        stats['instances'] += 1
        if lam == 0:
            continue
        stats['nontrivial'] += 1
        _, G, G2 = candidate_sets(n, D)
        c1 = any(set(Delta) <= G for (Delta, _) in hits)
        c2 = any(set(Delta) <= G2 for (Delta, _) in hits)
        if not c1:
            stats['C1_fail'] += 1
            print(f"FAIL C1: lambda={lam} D={[fmt_fd(f, names) for f in D]} D_a={[fmt_fd(f, names) for f in Da]} G={[fmt_fd(f, names) for f in G]} Deltas={[[fmt_fd(f, names) for f in Delta] for (Delta, _) in hits]}", flush=True)
        if not c2:
            stats['C2_fail'] += 1
            print(f"FAIL C2: lambda={lam} D={[fmt_fd(f, names) for f in D]} G2={[fmt_fd(f, names) for f in G2]} Deltas={[[fmt_fd(f, names) for f in Delta] for (Delta, _) in hits]}", flush=True)
        if stats['instances'] % 2000 == 0:
            print(f"  ... {time.time()-t0:.0f}s {stats}", flush=True)
    print("DONE", stats, f"{time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 200000
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    main(n, seconds, cap, seed)
