r"""Leveled sampler of inclusion-minimal feasible dropped sets (|Delta| <= maxk), any number of attributes (cap on families).
T1: every E in F(Psi) has E_c enforceable.  T2: some E in F(Psi) is locally generated.  Reports failures."""
import sys, time, random
from itertools import combinations
from weak_stats import families_between
from minloss_bruteforce import *

def random_instance2(n, rng, mmax):
    D = []
    for _ in range(rng.randint(3, mmax)):
        k = rng.choice([1, 1, 2, 2, 2, 3, 3])
        X = 0
        while bin(X).count('1') < k:
            X |= 1 << rng.randrange(n)
        A = rng.randrange(n)
        while X & (1 << A):
            A = rng.randrange(n)
        D.append((X, 1 << A))
    return D

def main(n, seconds, cap, seed, maxk, mmax):
    rng = random.Random(seed)
    names = [chr(ord('a') + i) for i in range(n)]
    t0 = time.time(); seen = set()
    stats = {'instances': 0, 'skipped': 0, 'min_Delta_nonplain': 0, 'T1_fail': 0, 'T2_fail': 0, 'sum_F': 0}
    while time.time() - t0 < seconds:
        D = random_instance2(n, rng, mmax)
        cltD = closure_table(D, n)
        if cltD[0] != 0:
            continue
        sig = tuple(cltD)
        if sig in seen:
            continue
        seen.add(sig)
        if realizable(cltD, n):
            continue
        Da = atomic_cover(cltD, n)
        if len(Da) > 16:
            continue
        FD = closed_sets(cltD, n)
        feasible = {}
        skip = False
        for k in range(1, maxk + 1):
            for Delta in combinations(Da, k):
                if any(D2 <= frozenset(Delta) for D2 in feasible):
                    continue  # has a feasible proper subset: not inclusion-minimal, skip
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
                continue
            stats['min_Delta_nonplain'] += 1; stats['sum_F'] += len(Es)
            crit = [Y for (Y, B) in atomic_cover(cltPsi, n) if not is_bcnf_schema(Y | B, cltPsi)]
            t1 = True; t2 = False
            for clt in Es:
                Ea = atomic_cover(clt, n)
                W_c = [f for f in Ea if f not in Da and any((f[0] & ~cltPsi[Y]) == 0 for Y in crit)]
                cltEc = closure_table(Psi + W_c, n)
                if cltEc == list(clt):
                    t2 = True
                elif not realizable(cltEc, n):
                    t1 = False
            if not t1:
                stats['T1_fail'] += 1
            if not t2:
                stats['T2_fail'] += 1
            if not t1 or not t2:
                print(f"{'T1' if not t1 else ''}{'T2' if not t2 else ''}-FAIL: D={[fmt_fd(f, names) for f in D]} Delta={sorted(fmt_fd(f, names) for f in Delta)} crit={[fmt_set(Y, names) for Y in crit]} |F|={len(Es)}", flush=True)
        if stats['instances'] % 200 == 0:
            print(f"  ... {time.time()-t0:.0f}s {stats}", flush=True)
    print("DONE", stats, f"{time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 50000
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 121
    maxk = int(sys.argv[5]) if len(sys.argv) > 5 else 3
    mmax = int(sys.argv[6]) if len(sys.argv) > 6 else 7
    main(n, seconds, cap, seed, maxk, mmax)
