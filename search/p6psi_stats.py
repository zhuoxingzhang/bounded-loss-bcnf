r"""For every Psi (closed choice) with F(Psi) = {enforceable closed E : E cap D_a = Psi} non-empty:
  some_E : some E in F(Psi) satisfies E = (Psi cup W_c(E))^+  (local weakenings generate E)
  min_E  : every inclusion-minimal E in F(Psi) satisfies it
Reported separately for optimal Psi (|Delta| = lambda) and non-optimal Psi."""
import sys, time, random
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "src"))   # the oracle layer minloss_bruteforce.py and weak_stats.py lives in src/
from weak_stats import random_instance
from minloss_bruteforce import *

def main(n, seconds, seed):
    rng = random.Random(seed)
    names = [chr(ord('a') + i) for i in range(n)]
    t0 = time.time(); seen = set()
    stats = {'instances': 0, 'Psi_opt': 0, 'Psi_nonopt': 0, 'some_fail_opt': 0, 'some_fail_nonopt': 0, 'min_fail_opt': 0, 'min_fail_nonopt': 0, 'Psi_plain': 0}
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
        Da = atomic_cover(cltD, n)
        FD = closed_sets(cltD, n)
        byPsi = {}
        for F in coarser_families(FD, n):
            clt = family_to_closure_table(F, n)
            if not realizable(clt, n):
                continue
            Psi = tuple(f for f in Da if clt[f[0]] & f[1])
            byPsi.setdefault(Psi, []).append(clt)
        if not byPsi:
            continue
        lam = min(len(Da) - len(Psi) for Psi in byPsi)
        for Psi, Es in byPsi.items():
            opt = (len(Da) - len(Psi) == lam)
            cltPsi = closure_table(list(Psi), n)
            if any(list(clt) == cltPsi for clt in Es):
                stats['Psi_plain'] += 1
                continue  # plain design exists: W = {} works
            crit = [Y for (Y, B) in atomic_cover(cltPsi, n) if not is_bcnf_schema(Y | B, cltPsi)]
            ok = []
            for clt in Es:
                Ea = atomic_cover(clt, n)
                W_c = [f for f in Ea if f not in Da and any((f[0] & ~cltPsi[Y]) == 0 for Y in crit)]
                ok.append(closure_table(list(Psi) + W_c, n) == list(clt))
            def inside(c1, c2): return all((c1[X] & ~c2[X]) == 0 for X in range(1 << n))
            minimal = [i for i, c in enumerate(Es) if not any(j != i and inside(Es[j], c) for j in range(len(Es)))]
            some = any(ok); mn = all(ok[i] for i in minimal)
            tag = 'opt' if opt else 'nonopt'
            stats['Psi_' + tag] += 1
            if not some:
                stats['some_fail_' + tag] += 1
                if stats['some_fail_' + tag] <= 2:
                    print(f"FAIL some ({tag}): D={[fmt_fd(f, names) for f in D]} Psi={[fmt_fd(f, names) for f in Psi]} crit={[fmt_set(Y, names) for Y in crit]} |F|={len(Es)}", flush=True)
            if not mn:
                stats['min_fail_' + tag] += 1
        if stats['instances'] % 100 == 0:
            print(f"  ... {time.time()-t0:.0f}s {stats}", flush=True)
    print("DONE", stats, f"{time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 71
    main(n, seconds, seed)
