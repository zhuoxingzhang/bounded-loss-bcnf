r"""Random search for instances where plain designs or key-complete designs are suboptimal.

For a closed FD set E (given by its closure table) the key-complete test uses the maximal
candidate decomposition G(E) = { S : (S, E[S]) in BCNF and the D-minimal keys of S are the
E-minimal keys of S }.  Declaring all D-minimal keys on G(E) is a key-complete BCNF design with
enforced set E iff the key FDs of G(E) generate E and G(E) is lossless for E (monotonicity in
the set of schemata makes the maximal choice sufficient).
"""
import sys, time, random
from minloss_bruteforce import *

def kc_feasible(cltE, cltD, n):
    G = []; keyfds = []
    for S in range(1, 1 << n):
        if not is_bcnf_schema(S, cltE):
            continue
        kE = minimal_keys_of(S, cltE); kD = minimal_keys_of(S, cltD)
        if set(kE) != set(kD):
            continue
        G.append(S)
        for K in kD:
            if K != S:
                keyfds.append((K, S))
    if closure_table(keyfds, n) != cltE:
        return False
    return lossless(G, keyfds, n)

def analyse_all(n, D, weights=None, cap=None):
    cltD = closure_table(D, n)
    Da = atomic_cover(cltD, n)
    if weights is None:
        weights = {fd: 1 for fd in Da}
    FD = closed_sets(cltD, n)
    fams = coarser_families(FD, n)
    if cap is not None and len(fams) > cap:
        return None
    best = best_plain = best_kc = None
    wit = {}
    for F in fams:
        clt = family_to_closure_table(F, n)
        if not realizable(clt, n):
            continue
        loss = sum(weights[fd] for fd in Da if not (clt[fd[0]] & fd[1]))
        if best is None or loss < best:
            best, wit['opt'] = loss, clt
        if is_plain(clt, Da, n) and (best_plain is None or loss < best_plain):
            best_plain, wit['plain'] = loss, clt
        if kc_feasible(clt, cltD, n) and (best_kc is None or loss < best_kc):
            best_kc, wit['kc'] = loss, clt
    return Da, best, best_plain, best_kc, wit, len(fams)

def random_instance(n, rng):
    m = rng.randint(2, 6)
    D = []
    for _ in range(m):
        A = rng.randrange(n)
        k = rng.choice([1, 1, 2, 2, 3])
        others = [i for i in range(n) if i != A]
        X = 0
        for i in rng.sample(others, min(k, len(others))):
            X |= 1 << i
        D.append((X, 1 << A))
    return D

def main(n, seconds, cap, seed):
    rng = random.Random(seed)
    names = [chr(ord('a') + i) for i in range(n)]
    t0 = time.time(); seen = set()
    stats = {"instances": 0, "nontrivial": 0, "plain_gap": 0, "kc_gap": 0, "skipped": 0}
    while time.time() - t0 < seconds:
        D = random_instance(n, rng)
        cltD = closure_table(D, n)
        if cltD[0] != 0:
            continue
        sig = tuple(cltD)
        if sig in seen:
            continue
        seen.add(sig)
        res = analyse_all(n, D, cap=cap)
        if res is None:
            stats["skipped"] += 1
            continue
        Da, lam, lam_p, lam_kc, wit, nf = res
        stats["instances"] += 1
        if lam == 0:
            continue
        stats["nontrivial"] += 1
        if lam_p is None or lam_p > lam:
            stats["plain_gap"] += 1
            print(f"PLAIN GAP lambda={lam} plain={lam_p} kc={lam_kc} |Da|={len(Da)} fams={nf} D_a={[fmt_fd(f, names) for f in Da]}", flush=True)
        if lam_kc is None or lam_kc > lam:
            stats["kc_gap"] += 1
            E = wit['opt']
            print(f"KC GAP lambda={lam} plain={lam_p} kc={lam_kc} |Da|={len(Da)} fams={nf} D_a={[fmt_fd(f, names) for f in Da]} optE_kept={[fmt_fd(f, names) for f in Da if E[f[0]] & f[1]]}", flush=True)
        if stats["instances"] % 100 == 0:
            print(f"  ... {time.time()-t0:.0f}s {stats}", flush=True)
    print("DONE", stats, f"{time.time()-t0:.0f}s")

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 20000
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    main(n, seconds, cap, seed)
