r"""Weaker forms of the candidate lemma.

G(D): generators and violators of D-critical schemata XA (X->A in D_a with (XA, D[XA]) not in BCNF).
Up*(G): closure of G under "phi is essential for some derivation of some psi in the current set":
        phi in Up*(G) iff exists psi in Up*(G), psi != phi, with psi in (D_a - {psi})^+ and psi notin (D_a - {psi, phi})^+.
Property C3: every optimal Delta intersects G (for lambda > 0).
Property C4: some optimal Delta is contained in Up*(G).
Property C5: some optimal Delta is contained in G cup Up1(G) (one level only).
"""
import sys, time, random
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))   # the oracle layer minloss_bruteforce.py and weak_stats.py lives in src/
from weak_stats import optimal_sets, random_instance
from minloss_bruteforce import *
from cand_stats import candidate_sets

def upward_closure(Da, G, n, levels=None):
    cur = set(G); level = 0
    while True:
        new = set()
        for psi in cur:
            rest = [f for f in Da if f != psi]
            clt = closure_table(rest, n)
            if not (clt[psi[0]] & psi[1]):
                continue  # psi has no derivation from the others
            for phi in rest:
                if phi in cur or phi in new:
                    continue
                clt2 = closure_table([f for f in rest if f != phi], n)
                if not (clt2[psi[0]] & psi[1]):
                    new.add(phi)
        if not new:
            return cur
        cur |= new; level += 1
        if levels is not None and level >= levels:
            return cur

def main(n, seconds, cap, seed):
    rng = random.Random(seed)
    names = [chr(ord('a') + i) for i in range(n)]
    t0 = time.time(); seen = set()
    stats = {'instances': 0, 'nontrivial': 0, 'C3_fail': 0, 'C4_fail': 0, 'C5_fail': 0, 'skipped': 0, 'sum_Da': 0, 'sum_G': 0, 'sum_Up': 0}
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
        _, G, _ = candidate_sets(n, D)
        Up = upward_closure(Da, G, n)
        Up1 = upward_closure(Da, G, n, levels=1)
        stats['sum_Da'] += len(Da); stats['sum_G'] += len(G); stats['sum_Up'] += len(Up)
        c3 = all(set(Delta) & G for (Delta, _) in hits)
        c4 = any(set(Delta) <= Up for (Delta, _) in hits)
        c5 = any(set(Delta) <= Up1 for (Delta, _) in hits)
        for name, ok in [('C3', c3), ('C4', c4), ('C5', c5)]:
            if not ok:
                stats[name + '_fail'] += 1
                print(f"FAIL {name}: lambda={lam} D={[fmt_fd(f, names) for f in D]} G={[fmt_fd(f, names) for f in G]} Up={[fmt_fd(f, names) for f in Up]} Deltas={[[fmt_fd(f, names) for f in Delta] for (Delta, _) in hits]}", flush=True)
        if stats['instances'] % 2000 == 0:
            print(f"  ... {time.time()-t0:.0f}s {stats}", flush=True)
    print("DONE", stats, f"{time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 200000
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    main(n, seconds, cap, seed)
