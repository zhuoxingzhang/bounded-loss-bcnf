r"""repair.py: the algorithm Repair(R, Sigma, w) of the paper (Alg. 2), on top of fdlib and drop.

Repair computes a lossless, dependency-preserving 3NF decomposition that is in BCNF whenever possible
(here: the BCNF construction when Sigma^+ is enforceable, else 3NF synthesis; the paper uses iConf),
collects the key dependencies of the BCNF schemata and of a minimum-loss design of every critical
schema (computed by Drop on the small schema), checks with one enforceability test whether the
collected key dependencies Gamma are enforceable, and falls back to Drop on the whole schema otherwise.
"""
import time
from fdlib import *
from drop import drop, DropResult

class RepairResult:
    def __init__(self, **kw):
        self.design = None
        self.loss = None
        self.mode = None          # 'bcnf' (no critical schema), 'repair', 'fallback'
        self.dec0 = None          # the 3NF decomposition
        self.critical = []        # (S, DropResult) per critical schema of dec0
        self.gamma = None         # FDSet of the assembled key dependencies
        self.exact = None         # for the fallback: exactness of Drop
        self.stats = {}
        self.__dict__.update(kw)

    def __repr__(self):
        return "RepairResult(mode=%s, loss=%s, |dec0|=%s, critical=%s, %s)" % (
            self.mode, self.loss, None if self.dec0 is None else len(self.dec0),
            [(popcount(S), r.loss, r.exact) for S, r in self.critical], self.stats)

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
            # Drop ran out of bounds on this schema: declare only its minimal keys (never fails)
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
    if ok:
        res.design = design_from_cover(Ga, U, R)
        res.loss = loss_of(Da, G, w)
        res.mode = "bcnf" if not crit_schemata else "repair"
        res.exact = all(r.exact for _, r in res.critical) if crit_schemata else True
    elif fallback:
        r = drop(n, Da, w, R=R, time_limit=time_limit, max_w=max_w, max_extra=max_extra, verbose=verbose)
        res.mode = "fallback"
        res.design, res.loss, res.exact = r.design, r.loss, r.exact
        res.stats["fallback"] = r.stats
        res.stats["fallback_lower_bound"] = r.lower_bound
        res.stats["fallback_heuristic"] = r.heuristic
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
