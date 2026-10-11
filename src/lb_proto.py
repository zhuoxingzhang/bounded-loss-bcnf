"""lb_proto.py: prototype of stronger lower bounds on the minimum loss from the requirement sets at the root.

Every BCNF design leaves unenforced at least one element of every requirement set Q(g, {}) of an obstruction g
(Prop. "Packing bound"), so the minimum weight of a hitting set of these requirement sets is a lower bound on the
loss. Three bounds are compared:
  packing:  the greedy packing of pairwise disjoint requirement sets (the bound of drop.py);
  dual:     a fractional packing by dual ascent on the hitting-set LP (any feasible dual is a lower bound);
  exact:    the minimum-weight hitting set by branch and bound with the dual bound, within a time limit.
usage: python lb_proto.py [--seconds 60] [set ...]
"""
import sys, time, random
from fdlib import *

def root_requirements(n, Da, w=None):
    """the requirement sets Q(g, {}) of the obstructions g, as frozensets of minimal FDs"""
    unc, crit = split_critical(Da)
    U = FDSet(n, unc)
    viol_of = {f: violators(Da, f[0] | (1 << f[1])) for f in crit}
    reqs = []
    for g in crit:
        if U.implies(g[0], g[1]):
            continue
        Yc = Da.closure(g[0])
        s = set()
        for h in crit:
            if h[0] & ~Yc == 0:
                s.add(h)
                s.update(viol_of[h])
        reqs.append(frozenset(s))
    return reqs

def packing(reqs, w=None):
    used, total = set(), 0
    for r in sorted(reqs, key=len):
        if not (r & used):
            used |= r
            total += min(_w(w, h) for h in r)
    return total

def _w(w, f):
    return 1 if w is None else w[f]

def dual_ascent(reqs, w=None, order=None):
    """a feasible dual of the hitting-set LP: raise y_r for the sets in the given order up to the smallest
    remaining slack of their elements; returns the bound sum(y_r)"""
    load = {}
    total = 0.0
    rs = sorted(reqs, key=len) if order is None else order
    for r in rs:
        slack = min(_w(w, h) - load.get(h, 0.0) for h in r)
        if slack > 1e-12:
            total += slack
            for h in r:
                load[h] = load.get(h, 0.0) + slack
    return total

def dual_best(reqs, w=None, tries=30, seed=0):
    rng = random.Random(seed)
    best = dual_ascent(reqs, w)
    rs = list(reqs)
    for i in range(tries):
        rng.shuffle(rs)
        rs.sort(key=lambda r: (len(r), rng.random()))
        best = max(best, dual_ascent(reqs, w, rs))
        rng.shuffle(rs)
        best = max(best, dual_ascent(reqs, w, list(rs)))
    return best

def exact_hitting_set(reqs, w=None, deadline=None, stats=None):
    """minimum-weight hitting set by branch and bound: branch on the smallest unhit set over its elements in
    decreasing frequency, bound with the dual ascent on the unhit sets. Returns (weight, exact)."""
    reqs = [r for r in reqs]
    best = [sum(_w(w, h) for h in set().union(*reqs))] if reqs else [0]
    timed_out = [False]
    nodes = [0]
    freq = {}
    for r in reqs:
        for h in r:
            freq[h] = freq.get(h, 0) + 1

    def rec(chosen, cost, unhit):
        nodes[0] += 1
        if deadline is not None and time.time() > deadline:
            timed_out[0] = True
            return
        if not unhit:
            if cost < best[0]:
                best[0] = cost
            return
        lb = cost + dual_ascent(unhit, w)
        if lb >= best[0]:
            return
        r = min(unhit, key=len)
        for h in sorted(r, key=lambda h: (-freq[h], h)):
            rest = [q for q in unhit if h not in q]
            rec(chosen | {h}, cost + _w(w, h), rest)
            if timed_out[0]:
                return

    rec(frozenset(), 0, reqs)
    if stats is not None:
        stats["hs_nodes"] = nodes[0]
    return best[0], not timed_out[0]

if __name__ == "__main__":
    import experiments
    secs = 60.0
    args = sys.argv[1:]
    if args[:1] == ["--seconds"]:
        secs = float(args[1]); args = args[2:]
    for name in args or ["abalone", "bridges(null)", "echo(null)", "ncvoter(null)"]:
        n, F, _ = load_any(dict(experiments.SETS)[name])
        Da = atomic_cover(F) if len(F) <= 2000 else FDSet(n, sorted(set(F.fds)))
        t0 = time.time()
        reqs = root_requirements(n, Da)
        t1 = time.time()
        pk = packing(reqs)
        du = dual_best(reqs)
        t2 = time.time()
        stats = {}
        ex, exact = exact_hitting_set(reqs, None, time.time() + secs, stats)
        t3 = time.time()
        sizes = sorted(len(r) for r in reqs)
        print("%-16s obstructions %4d, requirement sets of size %s..%s (median %s), %.1fs | packing %d | dual %.2f (%.1fs) | hitting set %s%s (%.1fs, %d nodes)" % (
            name, len(reqs), sizes[0] if sizes else "-", sizes[-1] if sizes else "-", sizes[len(sizes) // 2] if sizes else "-", t1 - t0,
            pk, du, t2 - t1, ex, "" if exact else " (not proved)", t3 - t2, stats["hs_nodes"]), flush=True)
