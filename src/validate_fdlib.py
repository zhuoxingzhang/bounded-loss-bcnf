r"""validate_fdlib.py: cross-check fdlib, drop and repair against the brute-force oracles on random
small instances (closure tables of minloss_bruteforce.py, exact lambda of weak_stats.optimal_sets).

Checks per instance:
  A  atomic cover of Sigma^+ (symbolic exchange algorithm) == brute force
  B  enforceability of Sigma^+ == realizable(closure table)
  C  minimal keys of R == brute force
  D  Drop: loss == lambda (exact oracle), returned design is a BCNF design (chase-lossless for E, locally
     enforced), its unenforced set is exactly delta, and (Psi cup W)^+ == E
  E  Repair: returns a BCNF design with loss >= lambda; mode 'bcnf' iff lambda == 0 and Sigma^+ enforceable
usage: python validate_fdlib.py [n=5] [seconds=120] [seed=1] [instances]   (stops after `seconds` or after
       `instances` instances, whichever comes first)
"""
import sys, time, random
from fdlib import *
import minloss_bruteforce as bf
from weak_stats import optimal_sets, random_instance
from drop import drop
from repair import repair

def to_atomic(D):
    out = []
    for (l, r) in D:
        for a in bits(r):
            out.append((l, a))
    return out

def main(n, seconds, seed, limit=None):
    rng = random.Random(seed)
    t0 = time.time()
    stats = {"instances": 0, "nontrivial": 0, "fail": 0, "repair_optimal": 0, "repair_fallback": 0, "drop_incomplete": 0}
    names = [chr(65 + i) for i in range(n)]
    while time.time() - t0 < seconds and (limit is None or stats["instances"] < limit):
        D = random_instance(n, rng)
        cltD = bf.closure_table(D, n)
        if cltD[0] != 0:
            continue
        stats["instances"] += 1
        F = FDSet(n, to_atomic(D))
        # A: atomic cover
        Da_bf = set((X, A.bit_length() - 1) for (X, A) in bf.atomic_cover(cltD, n))
        Da = atomic_cover(F)
        if set(Da.fds) != Da_bf:
            stats["fail"] += 1
            print("FAIL A atomic cover:", [bf.fmt_fd(f, names) for f in D], sorted(Da.fds), sorted(Da_bf))
            continue
        # B: enforceability of Sigma^+
        ok, U = enforceable(Da)
        if ok != bf.realizable(cltD, n):
            stats["fail"] += 1
            print("FAIL B enforceable:", [bf.fmt_fd(f, names) for f in D], ok)
            continue
        # C: minimal keys
        R = (1 << n) - 1
        keys = set(minimal_keys(Da, R))
        keys_bf = set(bf.minimal_keys_of(R, cltD))
        if keys != keys_bf:
            stats["fail"] += 1
            print("FAIL C keys:", [bf.fmt_fd(f, names) for f in D], keys, keys_bf)
            continue
        # D: Drop against the exact oracle
        r = optimal_sets(n, D)
        lam = r[0] if r is not None else None
        if lam is None:
            continue
        if lam > 0:
            stats["nontrivial"] += 1
        res = drop(n, Da, max_w=4, time_limit=60)
        if not res.exact:
            stats["drop_incomplete"] += 1
        if res.loss != lam:
            stats["fail"] += 1
            print("FAIL D loss:", [bf.fmt_fd(f, names) for f in D], "drop", res.loss, "lambda", lam, res)
            continue
        E = key_dependencies(n, res.design)
        Ea = atomic_cover(E)
        if not is_locally_enforced(res.design, Ea):
            stats["fail"] += 1
            print("FAIL D local enforcement:", [bf.fmt_fd(f, names) for f in D], res)
            continue
        if not chase_lossless(n, [S for S, _ in res.design], E):
            stats["fail"] += 1
            print("FAIL D soundness:", [bf.fmt_fd(f, names) for f in D], res)
            continue
        if set(unenforced(Da, E)) != set(res.delta):
            stats["fail"] += 1
            print("FAIL D unenforced set:", [bf.fmt_fd(f, names) for f in D], res, unenforced(Da, E))
            continue
        gen = FDSet(n, [f for f in Da.fds if f not in set(res.delta)] + res.W)
        if any(gen.closure(X) != E.closure(X) for X in range(1 << n)):
            stats["fail"] += 1
            print("FAIL D generated set:", [bf.fmt_fd(f, names) for f in D], res)
            continue
        # E: Repair
        rr = repair(n, F, Da=Da, max_w=4, time_limit=60)
        if rr.design is None or rr.loss < lam:
            stats["fail"] += 1
            print("FAIL E repair:", [bf.fmt_fd(f, names) for f in D], rr)
            continue
        E2 = key_dependencies(n, rr.design)
        Ea2 = atomic_cover(E2)
        if not is_locally_enforced(rr.design, Ea2) or not chase_lossless(n, [S for S, _ in rr.design], E2):
            stats["fail"] += 1
            print("FAIL E repair design:", [bf.fmt_fd(f, names) for f in D], rr)
            continue
        if loss_of(Da, E2) != rr.loss:
            stats["fail"] += 1
            print("FAIL E repair loss:", [bf.fmt_fd(f, names) for f in D], rr, loss_of(Da, E2))
            continue
        if (rr.mode == "bcnf") != (lam == 0):
            stats["fail"] += 1
            print("FAIL E repair mode:", [bf.fmt_fd(f, names) for f in D], rr, lam)
            continue
        if rr.loss == lam:
            stats["repair_optimal"] += 1
        if rr.mode == "fallback":
            stats["repair_fallback"] += 1
        if stats["instances"] % 200 == 0:
            print("  ...", "%.0fs" % (time.time() - t0), stats, flush=True)
    print("DONE", stats, "%.0fs" % (time.time() - t0), flush=True)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    limit = int(sys.argv[4]) if len(sys.argv) > 4 else None
    main(n, seconds, seed, limit)
