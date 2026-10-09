"""Exhaustive search over all FD sets (closure systems) on n attributes.
For each D: lambda, lambda_plain, and (optionally) lambda_keycomplete.
Reports instances where lambda_plain > lambda or lambda_keycomplete > lambda."""
import sys, time
from minloss_bruteforce import *

def all_closure_systems(n):
    full = (1 << n) - 1
    return coarser_families(frozenset([full]), n)

def fds_of_family(F, n):
    clt = family_to_closure_table(F, n)
    return [(X, clt[X] & ~X) for X in range(1 << n) if clt[X] != X]

def main(n, max_schemas, do_kc):
    fams = all_closure_systems(n)
    print(f"{len(fams)} closure systems on {n} attributes", flush=True)
    t0 = time.time()
    stats = {"total": 0, "nontrivial": 0, "plain_gap": 0, "kc_gap": 0}
    names = [chr(ord('a') + i) for i in range(n)]
    for idx, F in enumerate(fams):
        D = fds_of_family(F, n)
        cltD = family_to_closure_table(F, n)
        if cltD[0] != 0:      # skip closure systems with constant attributes
            continue
        Da = atomic_cover(cltD, n)
        if not Da:
            continue
        stats["total"] += 1
        _, lam, lam_p, E, Ep, _ = analyse(n, D, verbose=False)
        if lam == 0:
            continue
        stats["nontrivial"] += 1
        if lam_p is None or lam_p > lam:
            stats["plain_gap"] += 1
            print(f"PLAIN GAP: lambda={lam} lambda_plain={lam_p} D_a={[fmt_fd(f, names) for f in Da]}", flush=True)
        if do_kc:
            lam_kc, des = key_complete_designs(n, D, max_schemas=max_schemas, verbose=False)
            if lam_kc is None or lam_kc > lam:
                stats["kc_gap"] += 1
                print(f"KC GAP: lambda={lam} lambda_kc={lam_kc} D_a={[fmt_fd(f, names) for f in Da]}", flush=True)
        if idx % 200 == 0:
            print(f"  ... {idx}/{len(fams)} ({time.time()-t0:.0f}s) {stats}", flush=True)
    print("DONE", stats, f"{time.time()-t0:.0f}s")

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    max_schemas = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    do_kc = (sys.argv[3] != "0") if len(sys.argv) > 3 else True
    main(n, max_schemas, do_kc)
