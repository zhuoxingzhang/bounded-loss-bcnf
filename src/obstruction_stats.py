"""obstruction_stats.py: the two bounds of the paper on every FD set of the experiments.

For (R, Sigma) with uncritical minimal FDs U and critical minimal FDs C, the obstructions are O = Sigma_a - U^+
(Theorem "Obstruction bound": loss <= |O|). The requirement set of an obstruction g = Y -> B at Delta = {} is the set of
critical minimal FDs h with lhs(h) inside Y+ together with the violators of their schemata (Proposition "Packing bound":
a pairwise disjoint family of requirement sets gives loss >= its size under unit weights). When the requirement sets of
all obstructions are pairwise disjoint, both bounds coincide and the obstruction design is optimal (Corollary "Exact
loss from obstructions").

Prints one line per FD set and appends a record to results/obstructions.jsonl.
usage: python obstruction_stats.py [set name ...]
"""
import sys, os, json, time
from fdlib import FDSet, atomic_cover, split_critical, violators, CapExceeded
from experiments import SETS, MAX_MINIMAL, ASSUME_ATOMIC_ABOVE, load_any, bits

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)   # the repository root, which holds data/, results/ and iconf/

def analyse(name, path):
    t0 = time.time()
    n, F, names = load_any(path)
    rec = {"name": name, "n": n, "fds": len(F)}
    if len(F) > ASSUME_ATOMIC_ABOVE and all(not any(F.implies(X & ~(1 << a), A) for a in bits(X)) for (X, A) in F.fds):
        Da = FDSet(n, sorted(set(F.fds)))
        rec["atomic_assumed"] = True
    else:
        Da = atomic_cover(F, cap=MAX_MINIMAL)
    rec["minimal_fds"] = len(Da)
    unc, crit = split_critical(Da)
    U = FDSet(n, unc)
    obstructions = [g for g in crit if not U.implies(g[0], g[1])]
    rec["critical"] = len(crit)
    rec["obstructions"] = len(obstructions)
    viol_of = {f: violators(Da, f[0] | (1 << f[1])) for f in crit}
    reqs = []
    for g in obstructions:
        Yc = Da.closure(g[0])
        s = set()
        for h in crit:
            if h[0] & ~Yc == 0:
                s.add(h)
                s.update(viol_of[h])
        reqs.append(frozenset(s))
    # greedy packing (smallest sets first), as in drop.py
    used = set()
    packed = 0
    for r in sorted(reqs, key=len):
        if not (r & used):
            used |= r
            packed += 1
    disjoint = all(not (reqs[i] & reqs[j]) for i in range(len(reqs)) for j in range(i + 1, len(reqs)))
    rec["packing_lb"] = packed
    rec["requirements_disjoint"] = disjoint
    rec["exact_by_bounds"] = packed == len(obstructions)
    rec["max_requirement"] = max((len(r) for r in reqs), default=0)
    rec["seconds"] = round(time.time() - t0, 1)
    return rec

def main(argv):
    wanted = set(argv)
    out = os.path.join(ROOT, "results", "obstructions.jsonl")
    for name, path in SETS:
        if wanted and name not in wanted:
            continue
        if name in ("diabetic(null)", "fd-red") and not wanted:
            continue
        try:
            rec = analyse(name, path)
        except CapExceeded as e:
            rec = {"name": name, "error": str(e)}
        print("%-22s |Sa| %6s  critical %5s  obstructions %5s  packing_lb %5s  disjoint %-5s  exact %-5s  %ss" % (
            name, rec.get("minimal_fds", "-"), rec.get("critical", "-"), rec.get("obstructions", "-"),
            rec.get("packing_lb", "-"), rec.get("requirements_disjoint", "-"), rec.get("exact_by_bounds", "-"),
            rec.get("seconds", "-")), flush=True)
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

if __name__ == "__main__":
    main(sys.argv[1:])
