r"""
Brute-force verification tool for "BCNF with bounded dependency loss".

Definitions implemented exactly as in the paper draft (overleaf/main.tex):

* (R, D): attributes 0..n-1 as bitmasks, D a set of FDs.
* D_a: atomic cover = all minimal FDs X -> A in D^+ (A not in X, no proper subset of X determines A).
* A closed FD set E (a closure system coarser than D's) is *realizable* iff (R, E) has a lossless,
  dependency-preserving BCNF decomposition iff E has a cover of uncritical atomic FDs
  (X -> A in E_a is uncritical iff (XA, E[XA]) is in BCNF).
  Realizable closed sets are exactly the enforced-FD sets of BCNF designs (sound + locally enforced).
* loss(E) = |D_a \ E|  (unit weights; weighted variant via w).
* lambda(R, D) = min loss over realizable E;  lambda_plain = min over realizable E with E = (D_a cap E)^+.
* Key-complete designs: decomposition DD, every schema declares all D-minimal keys; E = closure of those
  key dependencies; valid iff lossless for E (chase) and each (S, E[S]) in BCNF.
"""
from itertools import combinations
import sys

def popcount(x):
    return bin(x).count("1")

def closure_fn(fds):
    """fds: list of (lhs_mask, rhs_mask). Returns a function X -> closure."""
    def cl(X):
        C = X
        changed = True
        while changed:
            changed = False
            for l, r in fds:
                if (l & ~C) == 0 and (r & ~C):
                    C |= r
                    changed = True
        return C
    return cl

def closure_table(fds, n):
    cl = closure_fn(fds)
    return [cl(X) for X in range(1 << n)]

def atomic_cover(clt, n):
    """All minimal FDs X -> A (as (X, A_mask)) of the closure table clt."""
    out = []
    for A in range(n):
        Am = 1 << A
        for X in range(1 << n):
            if X & Am:
                continue
            if not (clt[X] & Am):
                continue
            minimal = True
            for a in range(n):
                if X & (1 << a):
                    Y = X & ~(1 << a)
                    if clt[Y] & Am:
                        minimal = False
                        break
            if minimal:
                out.append((X, Am))
    return out

def closed_sets(clt, n):
    return frozenset(X for X in range(1 << n) if clt[X] == X)

def family_to_closure_table(F, n):
    """Closure operator of an intersection-closed family F containing the full set."""
    full = (1 << n) - 1
    clt = [0] * (1 << n)
    members = sorted(F)
    for X in range(1 << n):
        C = full
        for Y in members:
            if (X & ~Y) == 0 and popcount(Y) < popcount(C):
                C = Y
        clt[X] = C
    return clt

def coarser_families(FD, n):
    """Enumerate all intersection-closed families F with FD subset of F subset of P(R), full set in F.
    These are exactly the closure systems of closed FD sets E with E subset of D^+."""
    full = (1 << n) - 1
    base = set(FD)
    base.add(full)
    cands = [X for X in range(1 << n) if X not in base]
    cands.sort(key=lambda X: -popcount(X))  # decreasing size
    results = []
    def dfs(i, F, forced):
        if i == len(cands):
            results.append(frozenset(F))
            return
        X = cands[i]
        if X in forced:
            choices = [True]
        else:
            choices = [False, True]
        for inc in choices:
            if not inc:
                dfs(i + 1, F, forced)
            else:
                F2 = set(F)
                F2.add(X)
                forced2 = set(forced)
                forced2.discard(X)
                ok = True
                for Y in F:
                    Z = X & Y
                    if Z not in F2:
                        # Z is strictly smaller than X, hence later in the order (undecided)
                        forced2.add(Z)
                if ok:
                    dfs(i + 1, F2, forced2)
    dfs(0, set(base), set())
    return results

def is_bcnf_schema(S, clt):
    """(S, E[S]) in BCNF: every non-trivial FD Y -> B with Y, B inside S has Y a key of S."""
    sub = S
    # iterate over all subsets Y of S
    Y = sub
    while True:
        inside = clt[Y] & S
        if inside != Y:          # non-trivial FD inside S
            if (clt[Y] & S) != S:  # Y not a key of S
                return False
        if Y == 0:
            break
        Y = (Y - 1) & sub
    return True

def realizable(clt, n):
    """E (given by closure table) has an uncritical atomic cover?"""
    Ea = atomic_cover(clt, n)
    unc = [(X, A) for (X, A) in Ea if is_bcnf_schema(X | A, clt)]
    clU = closure_fn(unc)
    for X in range(1 << n):
        if clU(X) != clt[X]:
            return False
    return True

def is_plain(cltE, Da, n):
    kept = [(X, A) for (X, A) in Da if cltE[X] & A]
    clK = closure_fn(kept)
    for X in range(1 << n):
        if clK(X) != cltE[X]:
            return False
    return True

def analyse(n, D, weights=None, verbose=True):
    cltD = closure_table(D, n)
    Da = atomic_cover(cltD, n)
    if weights is None:
        weights = {fd: 1 for fd in Da}
    FD = closed_sets(cltD, n)
    fams = coarser_families(FD, n)
    best = None; best_plain = None
    best_E = None; best_plain_E = None
    for F in fams:
        clt = family_to_closure_table(F, n)
        if not realizable(clt, n):
            continue
        loss = sum(weights[fd] for fd in Da if not (clt[fd[0]] & fd[1]))
        if best is None or loss < best:
            best, best_E = loss, clt
        if is_plain(clt, Da, n):
            if best_plain is None or loss < best_plain:
                best_plain, best_plain_E = loss, clt
    if verbose:
        print(f"n={n}, |D_a|={len(Da)}, #coarser closure systems={len(fams)}")
        print("lambda        =", best)
        print("lambda_plain  =", best_plain)
    return Da, best, best_plain, best_E, best_plain_E, fams

# ---------- key-complete designs ----------

def minimal_keys_of(S, clt):
    keys = []
    Y = S
    while True:
        if (clt[Y] & S) == S:
            keys.append(Y)
        if Y == 0:
            break
        Y = (Y - 1) & S
    mins = [K for K in keys if not any((K2 & ~K) == 0 and K2 != K for K2 in keys)]
    return mins

def lossless(DD, fds, n):
    """Tableau chase: DD list of schema masks; fds list of (lhs, rhs). Lossless iff some row becomes full."""
    full = (1 << n) - 1
    # row values: dict attr -> symbol; distinguished = ('d', attr) ; else ('s', row, attr)
    rows = []
    for i, S in enumerate(DD):
        rows.append([('d', a) if (S >> a) & 1 else ('s', i, a) for a in range(n)])
    changed = True
    while changed:
        changed = False
        for l, r in fds:
            lattrs = [a for a in range(n) if (l >> a) & 1]
            rattrs = [a for a in range(n) if (r >> a) & 1]
            for i in range(len(rows)):
                for j in range(i + 1, len(rows)):
                    if all(rows[i][a] == rows[j][a] for a in lattrs):
                        for a in rattrs:
                            vi, vj = rows[i][a], rows[j][a]
                            if vi != vj:
                                # equate: prefer distinguished
                                keep = vi if vi[0] == 'd' else vj
                                drop = vj if keep is vi else vi
                                for row in rows:
                                    for b in range(n):
                                        if row[b] == drop:
                                            row[b] = keep
                                changed = True
    return any(all(rows[i][a][0] == 'd' for a in range(n)) for i in range(len(rows)))

def key_complete_designs(n, D, max_schemas=None, verbose=True):
    cltD = closure_table(D, n)
    Da = atomic_cover(cltD, n)
    full = (1 << n) - 1
    subsets = [S for S in range(1, 1 << n)]
    best = None; best_design = None
    sizes = range(1, (max_schemas or len(subsets)) + 1)
    for k in sizes:
        for DD in combinations(subsets, k):
            cov = 0
            for S in DD:
                cov |= S
            if cov != full:
                continue
            keyfds = []
            for S in DD:
                for K in minimal_keys_of(S, cltD):
                    if K != S:
                        keyfds.append((K, S))
            clt = closure_table(keyfds, n)
            if not all(is_bcnf_schema(S, clt) for S in DD):
                continue
            if not lossless(list(DD), keyfds, n):
                continue
            loss = sum(1 for (X, A) in Da if not (clt[X] & A))
            if best is None or loss < best:
                best, best_design = loss, (DD, keyfds)
    if verbose:
        print("lambda_keycomplete =", best, "design:", best_design)
    return best, best_design

def fmt_set(X, names):
    return "".join(names[a] for a in range(len(names)) if (X >> a) & 1) or "{}"

def fmt_fd(fd, names):
    return f"{fmt_set(fd[0], names)}->{fmt_set(fd[1], names)}"

if __name__ == "__main__":
    # Example A (weighted counterexample): R = {x1, x2, x3, a}, D = {x1x2x3->a, x1a->x2, a->x3}
    names = ["1", "2", "3", "a"]
    x1, x2, x3, a = 1, 2, 4, 8
    D = [(x1 | x2 | x3, a), (x1 | a, x2), (a, x3)]
    print("=== Example A: D = {123->a, 1a->2, a->3}")
    Da, lam, lam_p, E, Ep, fams = analyse(4, D)
    print("D_a =", [fmt_fd(f, names) for f in Da])
    w = {fd: (10 if fd == (x1 | x2 | x3, a) else 1) for fd in Da}
    print("--- weighted (w(123->a)=10, others 1)")
    analyse(4, D, weights=w)
    key_complete_designs(4, D)

    # Example B (unit-weight counterexample): R = {x1, x2, x2', x3, a}
    names = ["1", "2", "4", "3", "a"]   # 4 stands for x2'
    x1, x2, x2p, x3, a = 1, 2, 4, 8, 16
    D = [(x1 | x2 | x3, a), (x1 | x2p | x3, a), (x1 | a, x2), (x1 | a, x2p), (a, x3)]
    print("\n=== Example B: D = {123->a, 143->a, 1a->2, 1a->4, a->3}")
    Da, lam, lam_p, E, Ep, fams = analyse(5, D)
    print("D_a =", [fmt_fd(f, names) for f in Da])
    print("optimal E kept:", [fmt_fd(f, names) for f in Da if E[f[0]] & f[1]])
    print("best plain E kept:", [fmt_fd(f, names) for f in Da if Ep[f[0]] & f[1]])
    key_complete_designs(5, D, max_schemas=4)
