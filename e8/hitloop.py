"""Prototype of the implicit hitting-set loop for MinLoss.

Master: min w.y over y in {0,1}^Sa subject to cuts (P, Q):
    if every f in P is unenforced (y_f = 1), some f in Q is unenforced.
Solved here by enumeration in order of weight (an ILP/MaxSAT solver in practice).
Oracle: realise the chosen Delta (full: with weakenings, plain: without), else return cuts.
"""
import sys
from minloss import (table, minimal_fds, analyse, hits, complete_full, deltas_by_weight)


def violates(N, clS, g, S):
    Y, B = g
    YB = Y | (1 << B)
    return YB & S == YB and clS[Y] & S != S


def preprocess(N, Sigma):
    cl = table(N, Sigma)
    Sa = minimal_fds(N, cl)
    viol = {}
    for f in Sa:
        S = f[0] | (1 << f[1])
        viol[f] = [g for g in Sa if violates(N, cl, g, S)]
    U = [f for f in Sa if not viol[f]]
    return cl, Sa, viol, U


def requirement_cuts(N, cl, Sa, viol, U, Delta):
    """Prop. Packing bound: (Delta, Q(g, Delta)) for every g not implied by U u C(Delta) u Delta."""
    Dset = set(Delta)
    C = [f for f in Sa if viol[f] and all(v in Dset for v in viol[f])]
    base = table(N, U + C + list(Delta))
    UC = set(U) | set(C)
    cuts = []
    for g in Sa:
        Y, B = g
        if (base[Y] >> B) & 1:
            continue
        Yp = cl[Y]
        Q = set()
        for f in Sa:
            if f in Dset:
                continue
            if f not in UC and f[0] & Yp == f[0]:
                Q.add(f)
        for h in Sa:
            if viol[h] and h not in C and h[0] & Yp == h[0]:
                for v in viol[h]:
                    if v not in Dset:
                        Q.add(v)
        cuts.append((frozenset(Dset), frozenset(Q)))
    return cuts


def derivation(N, Psi, f):
    """A minimal subset D of Psi that implies f."""
    X, A = f
    D = list(Psi)
    for h in list(D):
        T = [k for k in D if k != h]
        if (table(N, T)[X] >> A) & 1:
            D = T
    return D


def satisfied(cut, lost):
    P, Q = cut
    return not P <= lost or bool(Q & lost)


def hitloop(N, Sigma, w=None, mode="full", trace=False):
    cl, Sa, viol, U = preprocess(N, Sigma)
    if w is None:
        w = {f: 1 for f in Sa}
    elif callable(w):
        w = {f: w(f) for f in Sa}
    cuts = requirement_cuts(N, cl, Sa, viol, U, [])
    order = deltas_by_weight(Sa, [w[f] for f in Sa])
    bounds = []
    it = 0
    while True:
        it += 1
        # master: lightest Delta satisfying every cut
        for wt, D in order:
            lost = frozenset(Sa[i] for i in D)
            if all(satisfied(c, lost) for c in cuts):
                break
        else:
            return None, bounds, it
        bounds.append(wt)
        Delta = list(lost)
        Psi = [f for f in Sa if f not in lost]
        clPsi = table(N, Psi)
        implied = [f for f in Delta if (clPsi[f[0]] >> f[1]) & 1]
        if implied:  # (a) closedness cuts
            for f in implied:
                cuts.append((frozenset([f]), frozenset(derivation(N, Psi, f))))
            continue
        if mode == "plain":
            ok = analyse(N, clPsi)[0]
            gens = Psi if ok else None
        else:
            gens = complete_full(N, Psi, Delta)
        if gens is not None:
            return wt, bounds, it
        new = requirement_cuts(N, cl, Sa, viol, U, Delta)
        cuts.extend(new)
        cuts.append((lost, frozenset(Sa) - lost))  # no-good
