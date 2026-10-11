r"""Price of soundness: can a decomposition that is lossless for D and in BCNF for D, with every schema
enforcing D[S] through its D-minimal keys (an unsound classical design), lose fewer minimal FDs than lambda(R, D)?

For each random instance: lambda by the level-wise exact solver; min over decompositions DD (up to max_schemas
schemata, all (S, D[S]) in BCNF, DD lossless for D) of |D_a - E'| with E' = closure of the key dependencies
of the D-minimal keys of the schemata.  A witness has min < lambda.
"""
import sys, time, random
from itertools import combinations
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))   # the oracle layer minloss_bruteforce.py and weak_stats.py lives in src/
from weak_stats import optimal_sets, random_instance
from minloss_bruteforce import *

def classical_min_loss(n, D, max_schemas):
    cltD = closure_table(D, n)
    Da = atomic_cover(cltD, n)
    full = (1 << n) - 1
    B = [S for S in range(1, 1 << n) if is_bcnf_schema(S, cltD)]
    keyfds_of = {S: [(K, S) for K in minimal_keys_of(S, cltD) if K != S] for S in B}
    best = None; best_DD = None
    for k in range(1, max_schemas + 1):
        for DD in combinations(B, k):
            cov = 0
            for S in DD:
                cov |= S
            if cov != full:
                continue
            if any((S & ~T) == 0 and S != T for S in DD for T in DD):
                continue  # redundant schema
            if not lossless(list(DD), D, n):
                continue
            keyfds = [f for S in DD for f in keyfds_of[S]]
            clt = closure_table(keyfds, n)
            loss = sum(1 for (X, A) in Da if not (clt[X] & A))
            if best is None or loss < best:
                best, best_DD = loss, (DD, keyfds)
    return best, best_DD

def main(n, seconds, max_schemas, seed):
    rng = random.Random(seed)
    names = [chr(ord('a') + i) for i in range(n)]
    t0 = time.time(); seen = set()
    stats = {'instances': 0, 'nontrivial': 0, 'witness': 0, 'equal': 0, 'classical_worse': 0}
    while time.time() - t0 < seconds:
        D = random_instance(n, rng)
        cltD = closure_table(D, n)
        if cltD[0] != 0:
            continue
        sig = tuple(cltD)
        if sig in seen:
            continue
        seen.add(sig)
        r = optimal_sets(n, D)
        lam, Da, hits = r
        stats['instances'] += 1
        if lam == 0:
            continue
        stats['nontrivial'] += 1
        cl, dd = classical_min_loss(n, D, max_schemas)
        if cl is not None and cl < lam:
            stats['witness'] += 1
            print(f"WITNESS: lambda={lam} classical={cl} D={[fmt_fd(f, names) for f in D]} D_a={[fmt_fd(f, names) for f in Da]} DD={[fmt_set(S, names) for S in dd[0]]} keys={[fmt_fd(f, names) for f in dd[1]]}", flush=True)
        elif cl == lam:
            stats['equal'] += 1
        else:
            stats['classical_worse'] += 1
        if stats['nontrivial'] % 20 == 0:
            print(f"  ... {time.time()-t0:.0f}s {stats}", flush=True)
    print("DONE", stats, f"{time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    max_schemas = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    main(n, seconds, max_schemas, seed)
