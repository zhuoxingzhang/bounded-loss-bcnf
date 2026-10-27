r"""Cover condition (Lem. 5.3 of the paper) and its pruning power.

U(D): uncritical minimal FDs of D.  C(Delta): critical minimal FDs X->A of D with a violator of XA in Delta.
NC(Delta): U cup C(Delta) cup Delta is a cover of D.
Checks on random instances with lambda > 0 (brute force over all enforceable E):
  NC_fail: some enforceable E whose Delta violates NC (must be 0 if the proof is right).
At the optimal level k = lambda, among all closed choices Delta (|Delta| = k, D_a - Delta implies nothing in Delta):
  n_closed, n_hitG (Delta meets G), n_NC (passes NC), n_opt (actually the dropped set of an optimal enforceable E).
"""
import sys, time, random
from itertools import combinations
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))   # the oracle layer minloss_bruteforce.py and weak_stats.py lives in src/
from weak_stats import random_instance
from minloss_bruteforce import *
from cand_stats import candidate_sets
from cand3_stats import critical_groups

def nc_holds(Delta, Da, U, groups, cltD, n):
    C = [g for (g, viol) in groups if any(v in Delta for v in viol)]
    cl = closure_fn(list(U) + C + list(Delta))
    return all(cl(X) == cltD[X] for X in range(1 << n))

def main(n, seconds, seed):
    rng = random.Random(seed)
    names = [chr(ord('a') + i) for i in range(n)]
    t0 = time.time(); seen = set()
    stats = {'instances': 0, 'nontrivial': 0, 'NC_fail': 0, 'n_closed': 0, 'n_hitG': 0, 'n_NC': 0, 'n_opt': 0, 'inst_NC_exact': 0}
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
        U = [f for f in Da if is_bcnf_schema(f[0] | f[1], cltD)]
        FD = closed_sets(cltD, n)
        best = None; sets = set()
        for F in coarser_families(FD, n):
            clt = family_to_closure_table(F, n)
            if not realizable(clt, n):
                continue
            Delta = frozenset((X, A) for (X, A) in Da if not (clt[X] & A))
            sets.add(Delta)
            if best is None or len(Delta) < best:
                best = len(Delta)
        for Delta in sets:
            if not nc_holds(Delta, Da, U, groups, cltD, n):
                stats['NC_fail'] += 1
                print(f"FAIL NC: D={[fmt_fd(f, names) for f in D]} Delta={sorted(fmt_fd(f, names) for f in Delta)}", flush=True)
        opt = {Delta for Delta in sets if len(Delta) == best}
        n_closed = n_hit = n_nc = 0
        for Delta in combinations(Da, best):
            Psi = [f for f in Da if f not in Delta]
            cltPsi = closure_table(Psi, n)
            if any(cltPsi[X] & A for (X, A) in Delta):
                continue
            n_closed += 1
            Ds = frozenset(Delta)
            if Ds & G:
                n_hit += 1
            if nc_holds(Ds, Da, U, groups, cltD, n):
                n_nc += 1
        stats['n_closed'] += n_closed; stats['n_hitG'] += n_hit; stats['n_NC'] += n_nc; stats['n_opt'] += len(opt)
        if n_nc == len(opt):
            stats['inst_NC_exact'] += 1
        if stats['instances'] % 500 == 0:
            print(f"  ... {time.time()-t0:.0f}s {stats}", flush=True)
    print("DONE", stats, f"{time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 11
    main(n, seconds, seed)
