r"""Mechanism test. For every Psi (feasible, non-plain) and every inclusion-minimal E in F(Psi) whose local closure
E_c = (Psi cup W_c)^+ is NOT enforceable (so E is a would-be counterexample if Psi were optimal):
  undrop_any : some X->A in Delta makes (E cup {X->A})^+ enforceable   (then Delta was not inclusion-minimal feasible)
  undrop_src : this holds for some X->A that is weakened by a non-local uncritical minimal weakening X'->A of E outside E_c
Prints the cases where undrop_any fails: those would refute the 'un-drop' proof strategy and are candidate counterexamples."""
import sys, time, random
from weak_stats import random_instance
from minloss_bruteforce import *

def main(n, seconds, seed):
    rng = random.Random(seed)
    names = [chr(ord('a') + i) for i in range(n)]
    t0 = time.time(); seen = set()
    stats = {'instances': 0, 'bad_pairs': 0, 'undrop_any_fail': 0, 'undrop_src_fail': 0, 'bad_pairs_unit_opt': 0}
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
            Psi = frozenset(f for f in Da if clt[f[0]] & f[1])
            byPsi.setdefault(Psi, []).append(clt)
        if not byPsi:
            continue
        lam = min(len(Da) - len(Psi) for Psi in byPsi)
        def inside(c1, c2): return all((c1[X] & ~c2[X]) == 0 for X in range(1 << n))
        for Psi, Es in byPsi.items():
            cltPsi = closure_table(list(Psi), n)
            if any(list(clt) == cltPsi for clt in Es):
                continue
            Delta = [f for f in Da if f not in Psi]
            crit = [Y for (Y, B) in atomic_cover(cltPsi, n) if not is_bcnf_schema(Y | B, cltPsi)]
            for i, clt in enumerate(Es):
                if any(j != i and inside(Es[j], clt) for j in range(len(Es))):
                    continue  # not inclusion-minimal
                Ea = atomic_cover(clt, n)
                W_all = [f for f in Ea if f not in Da]
                W_c = [f for f in W_all if any((f[0] & ~cltPsi[Y]) == 0 for Y in crit)]
                cltEc = closure_table(list(Psi) + W_c, n)
                if cltEc == list(clt) or realizable(cltEc, n):
                    continue
                stats['bad_pairs'] += 1
                if len(Delta) == lam:
                    stats['bad_pairs_unit_opt'] += 1
                U = [f for f in Ea if is_bcnf_schema(f[0] | f[1], clt)]
                nonlocal_src = set()
                for (Xp, A) in U:
                    if (Xp, A) in Da or (Xp, A) in W_c or (cltEc[Xp] & A):
                        continue
                    for (X, A2) in Delta:
                        if A2 == A and (X & ~Xp) == 0 and X != Xp:
                            nonlocal_src.add((X, A2))
                any_ok = False; src_ok = False
                for f in Delta:
                    clt2 = closure_table([(X, clt[X]) for X in range(1 << n)] + [f], n)
                    if realizable(clt2, n):
                        any_ok = True
                        if f in nonlocal_src:
                            src_ok = True
                if not any_ok:
                    stats['undrop_any_fail'] += 1
                    print(f"UNDROP-FAIL: D={[fmt_fd(f, names) for f in D]} Psi={sorted(fmt_fd(f, names) for f in Psi)} Delta={[fmt_fd(f, names) for f in Delta]} lambda={lam} E_a={[fmt_fd(f, names) for f in Ea]} W_c={[fmt_fd(f, names) for f in W_c]}", flush=True)
                if not src_ok:
                    stats['undrop_src_fail'] += 1
        if stats['instances'] % 100 == 0:
            print(f"  ... {time.time()-t0:.0f}s {stats}", flush=True)
    print("DONE", stats, f"{time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 240
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 91
    main(n, seconds, seed)
