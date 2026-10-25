"""Exact MinLoss for small schemata (bitmask attributes), following Thm. Enforceable FD sets,
Lem. Cover condition and Lem. Goal-directed weakening of the paper.

An FD is (lhs_mask, rhs_index). A closed FD set is represented by its closure table cl[X].
"""
import itertools


def table(N, F):
    full = 1 << N
    cl = [0] * full
    for X in range(full):
        c = X
        changed = True
        while changed:
            changed = False
            for L, a in F:
                if L & c == L and not (c >> a) & 1:
                    c |= 1 << a
                    changed = True
        cl[X] = c
    return cl


def minimal_fds(N, cl):
    out = []
    for X in range(1 << N):
        c = cl[X]
        for a in range(N):
            if (X >> a) & 1 or not (c >> a) & 1:
                continue
            ok = True
            Y = X
            while Y:
                b = Y & -Y
                Y ^= b
                if (cl[X ^ b] >> a) & 1:
                    ok = False
                    break
            if ok:
                out.append((X, a))
    return out


def submasks(S):
    Z = S
    while True:
        yield Z
        if Z == 0:
            return
        Z = (Z - 1) & S


def bcnf(S, cl):
    for Z in submasks(S):
        c = cl[Z] & S
        if c != Z and c != S:
            return False
    return True


def analyse(N, cl):
    """Return (enforceable, minimal FDs, uncritical minimal FDs, critical FDs not implied by uncritical)."""
    mins = minimal_fds(N, cl)
    unc = [(X, a) for X, a in mins if bcnf(X | (1 << a), cl)]
    cu = table(N, unc)
    bad = [(X, a) for X, a in mins if not (cu[X] >> a) & 1]
    return (not bad), mins, unc, bad


def hits(cl, Delta):
    return any((cl[X] >> a) & 1 for X, a in Delta)


def weakenings(N, X, a, within):
    """X' with X < X' <= within, a not in X'."""
    base = within & ~(1 << a)
    if X & base != X:
        return []
    rest = base & ~X
    return [X | Z for Z in submasks(rest) if Z]


def complete_full(N, Psi, Delta, limit=200000):
    """Is there an enforceable E with Psi <= E, E cap Delta empty (any weakenings)? Goal-directed DFS."""
    seen = set()
    stack = [list(Psi)]
    while stack:
        gens = stack.pop()
        cl = table(N, gens)
        key = tuple(cl)
        if key in seen:
            continue
        seen.add(key)
        if len(seen) > limit:
            raise RuntimeError("limit")
        if hits(cl, Delta):
            continue
        ok, mins, unc, bad = analyse(N, cl)
        if ok:
            return gens
        Y, B = bad[0]
        for X, a in Delta:
            for Xp in weakenings(N, X, a, cl[Y]):
                if (cl[Xp] >> a) & 1:
                    continue
                stack.append(gens + [(Xp, a)])
    return None


def local_set(N, Psi, Delta):
    cl = table(N, Psi)
    ok, mins, unc, bad = analyse(N, cl)
    uncset = set(unc)
    crit = [f for f in mins if f not in uncset]
    L = set()
    for Y, B in crit:
        for X, a in Delta:
            for Xp in weakenings(N, X, a, cl[Y]):
                if not (cl[Xp] >> a) & 1:
                    L.add((Xp, a))
    return sorted(L)


def complete_restricted(N, Psi, Delta, L, limit=200000):
    """Is there W <= L with (Psi u W)^+ enforceable and disjoint from Delta?"""
    seen = set()
    stack = [list(Psi)]
    while stack:
        gens = stack.pop()
        cl = table(N, gens)
        key = tuple(cl)
        if key in seen:
            continue
        seen.add(key)
        if len(seen) > limit:
            raise RuntimeError("limit")
        if hits(cl, Delta):
            continue
        if analyse(N, cl)[0]:
            return gens
        for Xp, a in L:
            if not (cl[Xp] >> a) & 1:
                stack.append(gens + [(Xp, a)])
    return None


def deltas_by_weight(Sa, w):
    idx = range(len(Sa))
    subs = []
    for k in range(len(Sa) + 1):
        for D in itertools.combinations(idx, k):
            subs.append((sum(w[i] for i in D), D))
    subs.sort()
    return subs


def solve(N, Sigma, w=None, mode="full", all_optimal=False, maxk=None):
    """mode: full | plain | local. Returns (loss, [(Delta, gens), ...])."""
    Sa = minimal_fds(N, table(N, Sigma))
    if w is None:
        w = [1] * len(Sa)
    elif callable(w):
        w = [w(f) for f in Sa]
    best = None
    sols = []
    for wt, D in deltas_by_weight(Sa, w):
        if best is not None and wt > best:
            break
        if maxk is not None and len(D) > maxk:
            continue
        Delta = [Sa[i] for i in D]
        Psi = [Sa[i] for i in range(len(Sa)) if i not in D]
        if hits(table(N, Psi), Delta):
            continue
        if mode == "full":
            g = complete_full(N, Psi, Delta)
        elif mode == "plain":
            g = Psi if analyse(N, table(N, Psi))[0] else None
        else:
            g = complete_restricted(N, Psi, Delta, local_set(N, Psi, Delta))
        if g is not None:
            best = wt
            sols.append((Delta, g))
            if not all_optimal:
                break
    return best, sols, Sa


def parse(attrs, fds):
    idx = {c: i for i, c in enumerate(attrs)}
    out = []
    for s in fds:
        l, r = s.split("->")
        L = 0
        for c in l:
            L |= 1 << idx[c]
        for c in r:
            out.append((L, idx[c]))
    return len(attrs), out


def show(attrs, f):
    X, a = f
    return "".join(c for i, c in enumerate(attrs) if (X >> i) & 1) + "->" + attrs[a]
