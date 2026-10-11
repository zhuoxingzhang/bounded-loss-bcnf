r"""Exact solver by levels plus structural statistics of the weakenings that optimal designs need.

Level k: for every closed choice Delta of k minimal FDs (Psi = D_a - Delta, Psi^+ contains no element of Delta),
enumerate all intersection-closed families F with CL(D) subset of F subset of CL(Psi): these are exactly the
closed FD sets E with Psi subset of E subset of D^+.  Keep the enforceable ones with loss exactly k.
The first level with a hit gives lambda and ALL optimal enforceable sets.

For every optimal E: U = uncritical minimal FDs of E (a cover), W_unc = U - D_a (uncritical weakenings).
A generating set W' is an inclusion-minimal subset of W_unc with (Psi cup W')^+ = E.
Properties tested (instance satisfies P iff SOME optimal E with SOME generating W' satisfies P):
  P1   |W'| <= |Delta|
  P1'  every dropped FD X->A has at most one weakening X'->A in W'
  P2   every X'->A in W' has X' subset of Y for some LHS Y of a minimal FD of D
  P2k  every X'->A in W' has X' subset of Y for some LHS Y of a minimal FD of D or minimal key of R
  P3   every X'->A in W' has X' subset of X cup Y for some LHS Y of a minimal FD of D
  P4   every X'->A in W' has X' equal to the LHS of some minimal FD of D
  P5   every X'->A in W' has X' equal to the LHS of some minimal FD of D, or X' subset of the LHS of a minimal FD of Psi^+ that is critical for Psi^+
"""
import sys, time, random
from itertools import combinations
from minloss_bruteforce import *

def families_between(FD, FPsi, n):
    """All intersection-closed F with FD subset of F subset of FPsi (both intersection-closed, both contain the full set)."""
    cands = sorted(FPsi - FD, key=lambda X: -popcount(X))
    results = []
    def dfs(i, F, forced):
        if i == len(cands):
            results.append(frozenset(F))
            return
        X = cands[i]
        choices = [True] if X in forced else [False, True]
        for inc in choices:
            if not inc:
                dfs(i + 1, F, forced)
            else:
                F2 = set(F); F2.add(X)
                forced2 = set(forced); forced2.discard(X)
                for Y in F:
                    Z = X & Y
                    if Z not in F2:
                        forced2.add(Z)
                dfs(i + 1, F2, forced2)
    dfs(0, set(FD), set())
    return results

def optimal_sets(n, D, cap=None, verbose=False):
    """Returns (lambda, Da, list of (Delta, clt) for all optimal enforceable E), or None if cap exceeded."""
    cltD = closure_table(D, n)
    Da = atomic_cover(cltD, n)
    FD = closed_sets(cltD, n)
    for k in range(0, len(Da) + 1):
        hits = []
        for Delta in combinations(Da, k):
            Psi = [f for f in Da if f not in Delta]
            cltPsi = closure_table(Psi, n)
            if any(cltPsi[X] & A for (X, A) in Delta):
                continue  # not a closed choice
            FPsi = closed_sets(cltPsi, n)
            fams = families_between(FD, FPsi, n)
            if cap is not None and len(fams) > cap:
                return None
            for F in fams:
                clt = family_to_closure_table(F, n)
                loss = sum(1 for (X, A) in Da if not (clt[X] & A))
                if loss != k:
                    continue
                if realizable(clt, n):
                    hits.append((Delta, clt))
        if hits:
            return k, Da, hits
    return None

def generating_sets(Psi, W_unc, cltE, n, max_size=4):
    """Inclusion-minimal subsets W' of W_unc (size <= max_size) with (Psi cup W')^+ = E."""
    out = []
    for s in range(0, min(max_size, len(W_unc)) + 1):
        for Wp in combinations(W_unc, s):
            if any(set(prev) <= set(Wp) for prev in out):
                continue
            if closure_table(list(Psi) + list(Wp), n) == cltE:
                out.append(Wp)
    return out

def props_of(Wp, Delta, Da, cltD, cltPsi, n):
    lhs = {X for (X, _) in Da}
    keysR = set(minimal_keys_of((1 << n) - 1, cltD))
    # critical minimal FDs of Psi^+
    PsiA = atomic_cover(cltPsi, n)
    crit_lhs = {X for (X, A) in PsiA if not is_bcnf_schema(X | A, cltPsi)}
    def origin(fd):
        Xp, A = fd
        return [X for (X, A2) in Delta if A2 == A and (X & ~Xp) == 0 and X != Xp]
    p = {}
    p['P1'] = len(Wp) <= len(Delta)
    cnt = {}
    for fd in Wp:
        for X in origin(fd):
            cnt[(X, fd[1])] = cnt.get((X, fd[1]), 0) + 1
    p["P1'"] = all(c <= 1 for c in cnt.values())
    p['P2'] = all(any((Xp & ~Y) == 0 for Y in lhs) for (Xp, A) in Wp)
    p['P2k'] = all(any((Xp & ~Y) == 0 for Y in lhs | keysR) for (Xp, A) in Wp)
    p['P3'] = all(any(any((Xp & ~(X | Y)) == 0 for Y in lhs) for X in origin((Xp, A))) for (Xp, A) in Wp)
    p['P4'] = all(Xp in lhs for (Xp, A) in Wp)
    p['P5'] = all(Xp in lhs or any((Xp & ~Y) == 0 for Y in crit_lhs) for (Xp, A) in Wp)
    # P6: X' inside the Psi-closure of the LHS of some minimal FD of Psi^+ that is critical for Psi^+
    p['P6'] = all(any((Xp & ~cltPsi[Y]) == 0 for Y in crit_lhs) for (Xp, A) in Wp)
    # P6D: X' inside the D-closure of the LHS of some critical minimal FD of Psi^+
    p['P6D'] = all(any((Xp & ~cltD[Y]) == 0 for Y in crit_lhs) for (Xp, A) in Wp)
    # P7: X'A inside the Psi-closure of the LHS of some critical minimal FD Y -> B of Psi^+ (whole weakened FD embedded)
    p['P7'] = all(any(((Xp | A) & ~cltPsi[Y]) == 0 for Y in crit_lhs) for (Xp, A) in Wp)
    # P8: X' inside the D-closure of the LHS X of the unenforced FD X -> A it weakens
    p['P8'] = all(any((Xp & ~cltD[X]) == 0 for X in origin((Xp, A))) for (Xp, A) in Wp)
    return p

PROPS = ['P1', "P1'", 'P2', 'P2k', 'P3', 'P4', 'P5', 'P6', 'P6D', 'P7', 'P8']

def analyse_instance(n, D, cap=None):
    res = optimal_sets(n, D, cap=cap)
    if res is None:
        return None
    lam, Da, hits = res
    cltD = closure_table(D, n)
    sat = {P: False for P in PROPS}
    details = []
    for Delta, clt in hits:
        Psi = [f for f in Da if f not in Delta]
        cltPsi = closure_table(Psi, n)
        Ea = atomic_cover(clt, n)
        U = [f for f in Ea if is_bcnf_schema(f[0] | f[1], clt)]
        W_unc = [f for f in U if f not in Da]
        gens = generating_sets(Psi, W_unc, clt, n)
        for Wp in gens:
            p = props_of(Wp, Delta, Da, cltD, cltPsi, n)
            for P in PROPS:
                sat[P] = sat[P] or p[P]
            details.append((Delta, Wp, p))
    return lam, Da, hits, sat, details

def random_instance(n, rng, mmax=6):
    m = rng.randint(2, mmax)
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
    stats = {'instances': 0, 'nontrivial': 0, 'nonplain': 0, 'skipped': 0}
    fails = {P: 0 for P in PROPS}
    while time.time() - t0 < seconds:
        D = random_instance(n, rng)
        cltD = closure_table(D, n)
        if cltD[0] != 0:
            continue
        sig = tuple(cltD)
        if sig in seen:
            continue
        seen.add(sig)
        r = analyse_instance(n, D, cap=cap)
        if r is None:
            stats['skipped'] += 1
            continue
        lam, Da, hits, sat, details = r
        stats['instances'] += 1
        if lam == 0:
            continue
        stats['nontrivial'] += 1
        if any(len(Wp) > 0 for (_, Wp, _) in details) and not any(len(Wp) == 0 for (_, Wp, _) in details):
            stats['nonplain'] += 1
        for P in PROPS:
            if not sat[P]:
                fails[P] += 1
                print(f"FAIL {P}: lambda={lam} D={[fmt_fd(f, names) for f in D]} D_a={[fmt_fd(f, names) for f in Da]}", flush=True)
                for Delta, Wp, p in details:
                    print(f"     Delta={[fmt_fd(f, names) for f in Delta]} W'={[fmt_fd(f, names) for f in Wp]} props={ {k: v for k, v in p.items()} }", flush=True)
        if stats['instances'] % 100 == 0:
            print(f"  ... {time.time()-t0:.0f}s {stats} fails={fails}", flush=True)
    print("DONE", stats, "fails", fails, f"{time.time()-t0:.0f}s", flush=True)

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    seconds = int(sys.argv[2]) if len(sys.argv) > 2 else 600
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 200000
    seed = int(sys.argv[4]) if len(sys.argv) > 4 else 1
    main(n, seconds, cap, seed)
