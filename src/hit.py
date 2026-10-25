r"""hit.py: the algorithm Hit of the paper (Alg. "Hit"), an implicit hitting-set search for a BCNF design with minimum
loss that certifies lower bounds on the way (experiment E1).

The set Delta of minimal FDs that a BCNF design leaves unenforced satisfies every valid cut (P, Q): P is not inside
Delta or Q meets Delta (Lem. "Valid cuts"). Hit solves the master problem, a set Delta of minimum weight that
satisfies the cuts found so far, as an integer program (scipy.optimize.milp, HiGHS), and tests Delta:
  closed      if Psi = Sigma_a - Delta implies some f in Delta, it adds the cut ({f}, D_f) for every such f, where
              D_f is a subset of Psi that implies f, made minimal by removing elements one at a time;
  cover       if U + C(Delta) + Delta does not imply some minimal FD g, no design leaves exactly Delta unenforced
              (Lem. "Cover condition"), and it adds (Delta, Q(g, Delta)) for every such g and the no-good
              (Delta, Sigma_a - Delta);
  realizable  otherwise Delta is tested as in Drop: Psi^+ enforceable, or the goal-directed search for weakened FDs
              (search_W of drop.py, with the caps of E1). Success returns the design of Cor. "Canonical designs"
              for the uncritical minimal FDs of the enforced set, which is optimal; exhaustive failure adds the
              no-good.
The initial cuts are (empty, Q(g, empty)) for the obstructions g, and the optimum of every master problem is a lower
bound on the loss; the first one is the root bound, and its linear relaxation is recorded as well. When a cap stops
the search for weakened FDs, Delta may still be realizable: the no-good is added all the same, the certified bound
is capped at the weight of Delta, and the design that the run returns may not be optimal. A run also ends when the
bound reaches the loss of the best design of E1 (or of weighted.py), which proves that design optimal, or when the
time is up; a master problem stopped by the time limit contributes the dual bound of HiGHS.
With --core, the cuts of the cover test use, instead of Delta, its elements that can occur in a requirement set of g:
the critical minimal FDs with left-hand side inside Y^+ and their violators. Lem. "Valid cuts" holds for this subset
P of Delta, Q(g, P) = Q(g, Delta), and the cut applies to every superset of P. With --plain, Delta is realizable only if Psi^+ is enforceable (the plain
designs of Thm. "Correctness of Hit"). With --eager, a set Delta whose complement implies one of its elements also
gets the cuts of the cover test and the no-good, since it is not realizable and Lem. "Valid cuts" holds for every
Delta. With --greedy K, every set Delta of a master problem that fails is followed
by up to K sets obtained by adding elements to it greedily (most open cuts hit per weight) until it satisfies every
cut, each tested as above: they add cuts without solving a master problem, and the lightest realizable one is an
upper bound, which ends the run as soon as the master problem reaches it (a capped test ends the extensions and
adds nothing). --weights uses the violation weights of weighted.py.

usage: python src/hit.py [--time 3600] [--core] [--eager] [--greedy K] [--plain] [--weights] [--no-ub] <set> ...
       records in results/hit[_core][_eager][_plain][_greedy][_w]_<set>.json
"""
import sys, os, json, time
from itertools import combinations
from fdlib import *
import experiments as e
from drop import search_W


def minimal_support(n, D, f):
    """a subset of the FDs D that implies f and none of whose proper subsets obtained by removing one element does"""
    D = list(D)
    i = 0
    while i < len(D):
        rest = D[:i] + D[i + 1:]
        if FDSet(n, rest).implies(f[0], f[1]):
            D = rest
        else:
            i += 1
    return D


class Master:
    """the master problem: a set of minimal FDs of minimum weight that satisfies every cut (P, Q), as a 0-1 integer
    program sum_{f in Q} y_f - sum_{f in P} y_f >= 1 - |P|"""

    def __init__(self, w):
        self.w = list(w)
        self.cuts = []
        self.seen = set()

    def add(self, P, Q):
        key = (frozenset(P), frozenset(Q))
        if key in self.seen:
            return False
        self.seen.add(key)
        self.cuts.append(key)
        return True

    def satisfied(self, Delta):
        return all(not P <= Delta or Q & Delta for P, Q in self.cuts)

    def solve(self, time_limit, relax=False):
        """(status, bound, Delta): status "optimal" or "timeout"; bound is a lower bound on the optimum"""
        import numpy as np
        from scipy.optimize import milp, LinearConstraint, Bounds
        from scipy.sparse import coo_matrix
        m = len(self.w)
        r, c, v, lo = [], [], [], []
        for j, (P, Q) in enumerate(self.cuts):
            for i in Q:
                r.append(j); c.append(i); v.append(1.0)
            for i in P:
                r.append(j); c.append(i); v.append(-1.0)
            lo.append(1.0 - len(P))
        cons = []
        if self.cuts:
            A = coo_matrix((v, (r, c)), shape=(len(self.cuts), m)).tocsr()
            cons.append(LinearConstraint(A, np.array(lo), np.full(len(lo), np.inf)))
        res = milp(np.array(self.w, dtype=float), constraints=cons, bounds=Bounds(0, 1),
                   integrality=np.zeros(m) if relax else np.ones(m),
                   options={"time_limit": max(1.0, time_limit), "mip_rel_gap": 0, "presolve": True})
        if relax:
            return "optimal", res.fun, None
        bound = getattr(res, "mip_dual_bound", None)
        if bound is None or not np.isfinite(bound):
            bound = res.fun if res.status == 0 else 0.0
        if res.status != 0 or res.x is None:
            return "timeout", bound, None
        return "optimal", res.fun, frozenset(i for i in range(m) if res.x[i] > 0.5)


class EnumMaster(Master):
    """the master problem by enumeration in increasing size, for unit weights on tiny instances (tests without
    scipy)"""

    def solve(self, time_limit, relax=False):
        m = len(self.w)
        for k in range(m + 1):
            for D in combinations(range(m), k):
                D = frozenset(D)
                if self.satisfied(D):
                    return "optimal", float(k), D
        return "timeout", 0.0, None


def hit(n, Da, w=None, time_limit=3600, ub=None, core=False, plain=False, greedy=0, eager=False, max_w=e.MAX_W,
        max_extra=None, master=None, verbose=True):
    """Alg. "Hit" on the atomic cover Da with integer weights w (dict, default 1); returns a record"""
    t0 = time.time()
    deadline = t0 + time_limit
    R = (1 << n) - 1
    fds = list(Da.fds)
    m = len(fds)
    idx = {f: i for i, f in enumerate(fds)}
    wt = [1 if w is None else w[f] for f in fds]
    unc, crit = split_critical(Da)
    U = FDSet(n, unc)
    viol = {h: [idx[v] for v in violators(Da, h[0] | (1 << h[1]))] for h in crit}
    crit_i = [idx[h] for h in crit]
    vi = {idx[h]: viol[h] for h in crit}
    yp = {idx[g]: Da.closure(g[0]) for g in crit}
    H = {g: [h for h in crit_i if fds[h][0] & ~yp[g] == 0] for g in crit_i}   # critical FDs with LHS inside Y^+
    obstructions = [idx[g] for g in crit if not U.implies(g[0], g[1])]

    def C_of(P):
        return set(h for h in crit_i if all(v in P for v in vi[h]))

    def failing(P, C):
        F = FDSet(n, unc + [fds[h] for h in C] + [fds[i] for i in P])
        return [g for g in crit_i if g not in P and not F.implies(fds[g][0], fds[g][1])]

    def Q_of(g, P, C):
        Q = set()
        for h in H[g]:
            if h in C:
                continue
            if h not in P:
                Q.add(h)
            Q.update(v for v in vi[h] if v not in P)
        return Q

    rel = {g: set(H[g]).union(*[vi[h] for h in H[g]]) for g in crit_i}   # every element of every Q(g, P)

    def core_of(g, Delta):
        """Delta restricted to rel[g]: Q(g, .) is the same for both, since C(.) agrees on H[g], and g stays
        unimplied, since U + C(P) + P grows with P"""
        return Delta & rel[g]

    M = (master or Master)(wt)
    for g in obstructions:
        M.add((), Q_of(g, set(), set()))
    rec = {"minimal_fds": m, "critical": len(crit), "obstructions": len(obstructions), "upper_bound": ub,
           "time_limit": time_limit, "core": core, "plain": plain, "greedy": greedy, "eager": eager,
           "iterations": []}
    if master is None:
        rec["root_lp"] = round(M.solve(deadline - time.time(), relax=True)[1], 3)

    def test(Delta):
        """(outcome, design): adds the cuts that Delta violates; outcome is "closure", "cover", "realizable",
        "unrealizable" (no-good added) or "capped" (a cap of the search for weakened FDs, nothing added)"""
        new = 0
        for f in Delta:
            r = []
            if (Da.closure_without(fds[f][0], Delta, r) >> fds[f][1]) & 1:
                D = minimal_support(n, [fds[i] for i in r], fds[f])
                new += M.add((f,), [idx[h] for h in D])
        if new and not eager:
            return "closure", None
        fail = failing(Delta, C_of(Delta))
        for g in fail:
            P = core_of(g, Delta) if core else Delta
            M.add(P, Q_of(g, P, C_of(P)))
        if new or fail:
            M.add(Delta, set(range(m)) - Delta)
            return "closure" if new else "cover", None
        Psi = FDSet(n, [fds[i] for i in range(m) if i not in Delta])
        Pa = atomic_cover(Psi)
        ok, U2 = enforceable(Pa)
        if ok:
            return "realizable", design_from_cover(Pa, U2, R)
        if not plain:
            stats = {"nodes": 0, "candidates": 0, "pruned": 0, "extension": 0, "tested": 0}
            res, cut, _ = search_W(n, R, Psi, Pa, sorted(fds[i] for i in Delta), max_w, deadline, stats, max_extra)
            if res is not None:
                return "realizable", design_from_cover(res[2], res[3], R)
            if cut:
                return "capped", None
        M.add(Delta, set(range(m)) - Delta)
        return "unrealizable", None

    def extend(Delta):
        """Delta with elements added greedily, by violated cuts hit per weight, until it satisfies every cut"""
        D = set(Delta)
        while True:
            open_ = [Q for P, Q in M.cuts if P <= D and not Q & D]
            if not open_:
                return frozenset(D)
            cnt = {}
            for Q in open_:
                for x in Q:
                    cnt[x] = cnt.get(x, 0) + 1
            D.add(max(cnt, key=lambda x: (cnt[x] / wt[x], -x)))

    lb, cap, design, status = 0, None, None, "timeout"
    hub, hdesign = None, None      # the lightest design that the greedy extensions found
    t_master = t_test = 0.0
    while True:
        left = deadline - time.time()
        if left <= 0:
            break
        t1 = time.time()
        st, bound, Delta = M.solve(left)
        t_master += time.time() - t1
        lb = max(lb, int(-(-bound // 1) if abs(bound - round(bound)) > 1e-6 else round(bound)))
        if "root" not in rec:
            rec["root"] = lb
        it = {"lb": lb, "cuts": len(M.cuts), "seconds": round(time.time() - t0, 2)}
        rec["iterations"].append(it)
        if st != "optimal":
            break
        if ub is not None and lb >= ub:
            status = "optimal (upper bound)"
            break
        if hub is not None and lb >= hub:
            design, status = hdesign, "optimal"
            break
        it["delta"] = len(Delta)
        t1 = time.time()
        outcome, found = test(Delta)
        it["action"] = outcome
        if outcome == "realizable":
            design = found
            status = "optimal" if cap is None or cap >= lb else "capped"
            t_test += time.time() - t1
            break
        if outcome == "capped":
            M.add(Delta, set(range(m)) - Delta)
            cap = lb if cap is None else min(cap, lb)
        if greedy:
            D = Delta
            for _ in range(greedy):
                D = extend(D)
                o, found = test(D)
                if o == "realizable":
                    wD = sum(wt[i] for i in D)
                    if hub is None or wD < hub:
                        hub, hdesign = wD, found
                    break
                if o == "capped":
                    break
        t_test += time.time() - t1
        if verbose and len(rec["iterations"]) % 50 == 0:
            print("   it %d: lb %d, %d cuts, greedy %s, %.0fs" % (len(rec["iterations"]), lb, len(M.cuts), hub,
                                                                 time.time() - t0), flush=True)
    rec["lower_bound"] = lb if cap is None else min(lb, cap)
    rec["greedy_upper_bound"] = hub
    rec["status"] = status
    rec["seconds"] = round(time.time() - t0, 1)
    rec["seconds_master"] = round(t_master, 1)
    rec["seconds_test"] = round(t_test, 1)
    rec["cuts"] = len(M.cuts)
    if design is None and hdesign is not None:
        design = hdesign
    if design is not None:
        sound, local, _ = check_bcnf_design(n, design, Da)
        E = key_dependencies(n, design)
        rec.update({"loss": loss_of(Da, E, None if w is None else w), "unit_loss": loss_of(Da, E),
                    "schemata": len(design), "sound": sound, "local": local,
                    "design": [{"attrs": list(bits(S)), "keys": [list(bits(K)) for K in keys]} for S, keys in design]})
        assert sound and local and rec["loss"] >= rec["lower_bound"], rec
        assert status != "optimal" or rec["loss"] == rec["lower_bound"], rec
    return rec


def upper_bound(name, w):
    """the least loss of a design of E1 (unit weights) or of weighted.py (violation weights), or None"""
    if w is None:
        p = os.path.join(e.ROOT, "results", "e1_%s.jsonl" % e.safe(name))
        r = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()][-1]
        xs = [r.get(k) for k in ("repair_loss", "drop_loss") if r.get(k) is not None]
        return min(xs) if xs else None
    import weighted
    r = weighted.record(name)
    xs = [v["weighted_loss"] for v in r["modes"].values()] if r else []
    return min(xs) if xs else None


def main():
    args, names = sys.argv[1:], []
    opts = {"time": 3600.0, "core": False, "plain": False, "eager": False, "weights": False, "ub": True, "greedy": 0}
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--time", "--greedy"):
            opts[a[2:]] = float(args[i + 1]) if a == "--time" else int(args[i + 1]); i += 2; continue
        if a in ("--core", "--plain", "--eager", "--weights"):
            opts[a[2:]] = True
        elif a == "--no-ub":
            opts["ub"] = False
        else:
            names.append(a)
        i += 1
    for name in names:
        n, F, _ = load_any(e.fd_path(name))
        Da, _ = e.sigma_a(n, F)
        w = None
        if opts["weights"]:
            import weighted
            w = weighted.violation_weights(name, n, Da)
        ub = upper_bound(name, w) if opts["ub"] else None
        print("%s: %d minimal FDs, upper bound %s" % (name, len(Da), ub), flush=True)
        rec = {"set": name, "attributes": n}
        rec.update(hit(n, Da, w, opts["time"], ub, opts["core"], opts["plain"], opts["greedy"], opts["eager"],
                       max_extra=e.max_extra_for(n)))
        tag = "".join("_" + k for k in ("core", "eager", "plain", "greedy") if opts[k]) + ("_w" if w is not None else "")
        with open(os.path.join(e.ROOT, "results", "hit%s_%s.json" % (tag, e.safe(name))), "w", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        print("%s: %s, lower bound %s (root %s, LP %s), loss %s, %d iterations, %d cuts, %.0fs" % (
            name, rec["status"], rec["lower_bound"], rec.get("root"), rec.get("root_lp"), rec.get("loss"),
            len(rec["iterations"]), rec["cuts"], rec["seconds"]), flush=True)


if __name__ == "__main__":
    main()
