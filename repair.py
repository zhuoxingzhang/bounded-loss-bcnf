r"""repair.py: the algorithm Repair(R, Sigma, w) of the paper (Alg. 2), on top of fdlib and drop.

Repair computes a lossless, dependency-preserving 3NF decomposition that is in BCNF whenever possible
(here: the BCNF construction when Sigma^+ is enforceable, else 3NF synthesis; the paper uses iConf),
collects the key dependencies of the BCNF schemata and of a minimum-loss design of every critical
schema (computed by Drop on the small schema), checks with one enforceability test whether the
collected key dependencies Gamma are enforceable, and falls back to Drop on the whole schema otherwise.

The fallback never fails: it returns the lightest of (1) an enforceable subset of Gamma^+ found by the
greedy on the atomic cover of Gamma^+ within half of the budget, (2) the result of the global Drop within
the remaining budget (exact or greedy), and (3) the key-only design of R
(every minimal key declared on the single schema R, loss nu). The certified lower bound of the global Drop
is reported as `lower_bound`.
"""
import time
from fdlib import *
from drop import drop, DropResult, _weight, greedy_restarts, uncritical_fixpoint

class RepairResult:
    def __init__(self, **kw):
        self.design = None
        self.loss = None
        self.mode = None          # 'bcnf' (no critical schema), 'repair', 'fallback'
        self.dec0 = None          # the 3NF decomposition
        self.critical = []        # (S, DropResult) per critical schema of dec0
        self.gamma = None         # FDSet of the assembled key dependencies
        self.exact = None         # whether the loss is proved minimal
        self.lower_bound = None   # certified lower bound on lambda (fallback only)
        self.stats = {}
        self.__dict__.update(kw)

    def __repr__(self):
        return "RepairResult(mode=%s, loss=%s, exact=%s, lb=%s, |dec0|=%s, critical=%s, %s)" % (
            self.mode, self.loss, self.exact, self.lower_bound, None if self.dec0 is None else len(self.dec0),
            [(popcount(S), r.loss, r.exact) for S, r in self.critical], self.stats)

def key_only_design(n, Da, R, w=None):
    """the trivial BCNF design: the single schema R with all its minimal keys declared (loss nu)"""
    design = [(R, minimal_keys(Da, R))]
    return design, loss_of(Da, key_dependencies(n, design), w)

def repair(n, F, Da=None, w=None, time_limit=None, local_time_limit=None, max_w=4, max_extra=None, fallback=True, verbose=False):
    t0 = time.time()
    Da = atomic_cover(F) if Da is None else Da
    R = (1 << n) - 1
    dec0, bcnf_possible = synthesize_3nf_bcnf(F, Da)
    res = RepairResult(dec0=dec0, stats={})
    gamma = []
    crit_schemata = []
    for S in dec0:
        DaS = Da.restrict(S)
        if is_bcnf(Da, S):
            for K in minimal_keys(DaS, S):
                for b in bits(S & ~K):
                    gamma.append((K, b))
        else:
            crit_schemata.append(S)
    for S in crit_schemata:
        DaS = Da.restrict(S)
        r = drop(n, DaS, w, R=S, time_limit=local_time_limit, max_w=max_w, max_extra=max_extra, verbose=verbose)
        res.critical.append((S, r))
        if r.design is None:
            # Drop ran out of time on this schema: declare only its minimal keys (never fails)
            for K in minimal_keys(DaS, S):
                for b in bits(S & ~K):
                    gamma.append((K, b))
        else:
            gamma += key_dependencies(n, r.design).fds
    G = FDSet(n, gamma)
    res.gamma = G
    Ga = atomic_cover(G)
    ok, U = enforceable(Ga)
    res.stats["gamma_minimal_fds"] = len(Ga)
    res.stats["time_local"] = time.time() - t0
    if ok:
        res.design = design_from_cover(Ga, U, R)
        res.loss = loss_of(Da, G, w)
        res.mode = "bcnf" if not crit_schemata else "repair"
        res.exact = all(r.exact for _, r in res.critical) if crit_schemata else True
        if res.exact and crit_schemata:
            # the sum of the local optima is not a lower bound in general (see the paper), so exactness
            # of Repair is only claimed when every critical schema was solved exactly and the assembled
            # loss equals the sum of the local losses
            res.exact = res.loss == sum(r.loss for _, r in res.critical)
        if crit_schemata and res.loss > 0:
            # the obstruction design (Theorem "Obstruction bound": the closure of the uncritical minimal FDs of
            # Sigma is enforceable, loss = weight of the obstructions) is a polynomial baseline that the
            # assembled design must not fall below; Repair returns the lighter of the two
            t3 = time.time()
            fx = uncritical_fixpoint(n, Da, None, R, None, res.stats)
            res.stats["time_obstruction"] = time.time() - t3
            if fx is not None:
                d0 = design_from_cover(fx[2], fx[3], R)
                loss0 = loss_of(Da, key_dependencies(n, d0), w)
                res.stats["obstruction_loss"] = loss0
                if loss0 < res.loss:
                    res.design, res.loss = d0, loss0
                    res.exact = loss0 == 0
                    res.stats["obstruction_taken"] = True
    elif fallback:
        res.mode = "fallback"
        t1 = time.time()
        deadline = None if time_limit is None else t1 + time_limit
        candidates = []
        # (0) the uncritical fixpoints of Gamma^+ and of Sigma^+ (cheap: a few atomic covers each)
        for label, Xa in (("gamma-fix", Ga), ("sigma-fix", Da)):
            t3 = time.time()
            fx = uncritical_fixpoint(n, Xa, None, R, deadline, res.stats)
            res.stats["time_" + label] = time.time() - t3
            if fx is not None:
                d0 = design_from_cover(fx[2], fx[3], R)
                candidates.append((label, loss_of(Da, key_dependencies(n, d0), w), d0, None))
        # (1) an enforceable subset of Gamma^+ by the greedy (unit weights in the search, loss measured on Sigma_a)
        g = greedy_restarts(n, Ga, None, R, None if time_limit is None else t1 + time_limit / 2, res.stats)
        if g is not None:
            Delta1, Psi1, Pa1, U1 = g
            d1 = design_from_cover(Pa1, U1, R)
            candidates.append(("gamma", loss_of(Da, key_dependencies(n, d1), w), d1, None))
        res.stats["time_gamma_drop"] = time.time() - t1
        # (2) the global Drop with the remaining budget
        t2 = time.time()
        r2 = drop(n, Da, w, R=R, time_limit=None if deadline is None else max(10.0, deadline - t2), max_w=max_w, max_extra=max_extra, verbose=verbose)
        res.stats["fallback"] = r2.stats
        res.lower_bound = r2.lower_bound
        if r2.design is not None:
            candidates.append(("drop", r2.loss, r2.design, r2))
        res.stats["time_global_drop"] = time.time() - t2
        # (3) the key-only design
        d3, loss3 = key_only_design(n, Da, R, w)
        candidates.append(("keys", loss3, d3, None))
        stage, loss, design, r = min(candidates, key=lambda c: c[1])
        res.design, res.loss = design, loss
        res.exact = (stage == "drop" and r2.exact and not r2.heuristic) or (res.lower_bound is not None and loss <= res.lower_bound)
        res.stats["fallback_stage"] = stage
        res.stats["fallback_lower_bound"] = r2.lower_bound
        res.stats["fallback_heuristic"] = not res.exact
        res.stats["fallback_candidates"] = [(c[0], c[1]) for c in candidates]
    else:
        res.mode = "fallback-needed"
    res.stats["time"] = time.time() - t0
    return res

if __name__ == "__main__":
    C, S, T, Z = 0, 1, 2, 3
    F = FDSet(4, [(1 << C, S), (1 << C, T), ((1 << S) | (1 << T), Z), (1 << Z, T)])
    names = "CSTZ"
    r = repair(4, F)
    print(r)
    print("design:", [(fmt_set(S_, names), [fmt_set(K, names) for K in keys]) for S_, keys in r.design])
