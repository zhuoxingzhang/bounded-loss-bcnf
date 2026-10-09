r"""Universal form: for EVERY enforceable closed E inside D^+ (its own Psi = E cap D_a), is E_c = (Psi cup W_c)^+ enforceable,
where W_c = minimal FDs of E outside D_a whose LHS lies inside Y+_Psi for some minimal FD Y->B of Psi^+ critical for Psi^+?
Also the variant with W_c restricted to E-uncritical weakenings (W_cu)."""
import sys, time, random
from weak_stats import random_instance
from minloss_bruteforce import *

def main(n, seconds, seed):
    rng = random.Random(seed)
    names = [chr(ord('a') + i) for i in range(n)]
    t0 = time.time(); seen = set()
    stats = {'instances': 0, 'sets': 0, 'nontrivial_sets': 0, 'Ec_fail': 0, 'Ecu_fail': 0, 'Ec_eq_E': 0}
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
        for F in coarser_families(FD, n):
            clt = family_to_closure_table(F, n)
            if not realizable(clt, n):
                continue
            stats['sets'] += 1
            Ea = atomic_cover(clt, n)
            W_all = [f for f in Ea if f not in Da]
            if not W_all:
                continue
            stats['nontrivial_sets'] += 1
            Psi = [f for f in Da if clt[f[0]] & f[1]]
            cltPsi = closure_table(Psi, n)
            crit = [Y for (Y, B) in atomic_cover(cltPsi, n) if not is_bcnf_schema(Y | B, cltPsi)]
            W_c = [f for f in W_all if any((f[0] & ~cltPsi[Y]) == 0 for Y in crit)]
            W_cu = [f for f in W_c if is_bcnf_schema(f[0] | f[1], clt)]
            cltEc = closure_table(Psi + W_c, n)
            cltEcu = closure_table(Psi + W_cu, n)
            if cltEc == list(clt):
                stats['Ec_eq_E'] += 1
            if not realizable(cltEc, n):
                stats['Ec_fail'] += 1
                if stats['Ec_fail'] <= 3:
                    print(f"FAIL Ec: D={[fmt_fd(f, names) for f in D]} E_a={[fmt_fd(f, names) for f in Ea]} Psi={[fmt_fd(f, names) for f in Psi]} crit={[fmt_set(Y, names) for Y in crit]} W_c={[fmt_fd(f, names) for f in W_c]}", flush=True)
            if not realizable(cltEcu, n):
                stats['Ecu_fail'] += 1
        if stats['instances'] % 200 == 0:
            print(f"  ... {time.time()-t0:.0f}s {stats}", flush=True)
    print("DONE", stats, f"{time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 61
    main(n, seconds, seed)
