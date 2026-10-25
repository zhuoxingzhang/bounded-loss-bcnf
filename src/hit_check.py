r"""hit_check.py: Hit (hit.py) against the exact minimum loss of the brute-force oracle (weak_stats.optimal_sets) on
random small instances, with the cuts of the paper and with --core, and the running example. A run whose search
for weakened FDs hit a cap of E1 must still bracket the minimum between its certified bound and its loss.

usage: python src/hit_check.py [n=5] [seconds=60] [seed=1]
"""
import sys, time, random
from fdlib import *
from weak_stats import optimal_sets, random_instance
import minloss_bruteforce as bf
from hit import hit, EnumMaster
from validate_fdlib import to_atomic

def main(n, seconds, seed):
    C, S, T, Z = 1, 2, 4, 8
    Da = atomic_cover(FDSet(4, [(C, 1), (C, 2), (S | T, 3), (Z, 2)]))
    r = hit(4, Da, master=EnumMaster, verbose=False)
    print("running example: loss %s, %s, %d iterations" % (r.get("loss"), r["status"], len(r["iterations"])))
    rng = random.Random(seed)
    t0 = time.time()
    stats = {"instances": 0, "lossy": 0, "root_optimal": 0, "capped": 0, "fail": 0}
    while time.time() - t0 < seconds:
        D = random_instance(n, rng)
        if bf.closure_table(D, n)[0] != 0:
            continue
        o = optimal_sets(n, D)
        if o is None:
            continue
        lam = o[0]
        Da = atomic_cover(FDSet(n, to_atomic(D)))
        stats["instances"] += 1
        stats["lossy"] += lam > 0
        for core in (False, True):
            r = hit(n, Da, core=core, master=EnumMaster, verbose=False)
            if r["status"] == "capped" and r["lower_bound"] <= lam <= r["loss"]:
                stats["capped"] += 1
            elif r["status"] != "optimal" or r["loss"] != lam:
                stats["fail"] += 1
                print("FAIL", [bf.fmt_fd(f, "ABCDEFG") for f in D], "lambda", lam, "core", core, r["status"],
                      r.get("loss"), r["lower_bound"])
        stats["root_optimal"] += r["root"] == lam
    print("DONE", stats, "%.0fs" % (time.time() - t0))

if __name__ == "__main__":
    a = sys.argv[1:]
    main(int(a[0]) if a else 5, float(a[1]) if len(a) > 1 else 60, int(a[2]) if len(a) > 2 else 1)
