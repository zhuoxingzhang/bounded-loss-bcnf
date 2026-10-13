r"""weighted.py: Repair and Drop under weights that estimate how often each minimal FD is at risk (runs on the server).

The weight of a minimal FD f of Sigma_a is one plus the number of updates that violate f among the random updates of
the weighting seeds (default 6..10, 10,000 updates each, drawn as in e4.py). Repair and Drop then run with these
weights and the parameters of E1 (experiments.py). The designs are evaluated as in E4 on the evaluation seeds
(default 1..5, the seeds of e4.py), which are disjoint from the weighting seeds, together with the unit-weight designs
of Repair and Drop from the E1 record, so that every design meets the same updates.

For every design the record holds the unit loss (the number of unenforced minimal FDs), the weighted loss, and per
evaluation seed the missed harmful updates, the integrity risk and the false rejections.

usage: python3 weighted.py [--updates 10000] [--wseeds 6,7,8,9,10] [--seeds 1,2,3,4,5] [set ...]
       records in results/weighted_<set>.jsonl
       python3 weighted.py --table
"""
import sys, os, json, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdlib import *
import experiments
from experiments import (load_any, max_extra_for, design_json, LOCAL_TIME, DROP_TIME, ASCEND_TIME, MAX_W,
                         DROP_MAX_MINIMAL, MAX_MINIMAL, ASSUME_ATOMIC_ABOVE)
from drop import drop
import drop as drop_module
from repair import repair
from iconf import iconf_decomposition
from e3 import SETS, e1_record
import e4

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

class Weights(dict):
    """the weights of the minimal FDs; an FD outside the table weighs one"""
    def __missing__(self, f):
        return 1

def atomic_cover_of(F, n):
    """Sigma_a exactly as experiments.run computes it"""
    if len(F) > ASSUME_ATOMIC_ABOVE and all(not any(F.implies(X & ~(1 << a), A) for a in bits(X)) for (X, A) in F.fds):
        return FDSet(n, sorted(set(F.fds)))
    return atomic_cover(F, cap=MAX_MINIMAL)

def fd_list(Da):
    return [(tuple(bits(X)), A) for (X, A) in Da.fds]

def risk_of(codes, n, sigma, design, updates, seeds, cache):
    """per seed: harmful updates, missed ones, risk and false rejections of the design"""
    kd = e4.key_dependencies_of(design)
    out = []
    for seed in seeds:
        upd_row, upd_attr, upd_val, mult, harmful = cache[seed]
        caught = e4.violations(codes, mult, kd, upd_row, upd_attr, upd_val).any(axis=1)
        missed = harmful & ~caught
        out.append({"seed": seed, "harmful": int(harmful.sum()), "missed": int(missed.sum()),
                    "risk": float(missed.sum() / harmful.sum()) if harmful.sum() else 0.0,
                    "false_rejections": int((caught & ~harmful).sum())})
    return out

def run(name, updates, wseeds, seeds):
    rec0 = e1_record(name)
    path = experiments.fd_path(SETS[name])
    n, F, _ = load_any(path)
    Da = atomic_cover_of(F, n)
    assert len(Da) == rec0["minimal_fds"], (len(Da), rec0["minimal_fds"])
    t0 = time.time()
    codes = e4.load_table(name)
    sigma = fd_list(Da)
    out = {"set": name, "rows": int(codes.shape[0]), "attributes": n, "minimal_fds": len(Da), "updates": updates,
           "weight_seeds": wseeds, "eval_seeds": seeds}
    # the weights: one plus the number of violating updates over the weighting seeds
    counts = np.zeros(len(sigma), dtype=np.int64)
    for seed in wseeds:
        upd_row, upd_attr, upd_val, mult = e4.draw_updates(codes, n, updates, seed)
        counts += e4.violations(codes, mult, sigma, upd_row, upd_attr, upd_val).sum(axis=0)
    w = Weights()
    for f, c in zip(Da.fds, counts):
        w[f] = 1 + int(c)
    out["time_weights"] = round(time.time() - t0, 1)
    out["weights"] = {"zero_count": int((counts == 0).sum()), "max": int(counts.max()) + 1,
                      "total": int(counts.sum()) + len(sigma)}
    print("%s: %d minimal FDs, %d never violated, weight max %d (%.0fs)" % (
        name, len(sigma), out["weights"]["zero_count"], out["weights"]["max"], out["time_weights"]), flush=True)
    # weighted Repair and Drop with the parameters of E1
    designs = {}
    t1 = time.time()
    dec = iconf_decomposition(n, Da)
    rr = repair(n, F, Da=Da, w=w, local_time_limit=LOCAL_TIME, time_limit=DROP_TIME, max_w=MAX_W,
                max_extra=max_extra_for(n), ascend_time=ASCEND_TIME, dec0=dec)
    out["repair_w"] = {"mode": rr.mode, "exact": rr.exact, "time": round(time.time() - t1, 1),
                       "stage": rr.stats.get("success_stage") or rr.stats.get("fallback_stage")}
    if rr.design is not None:
        designs["repair_w"] = rr.design
    print("%s: weighted Repair %s, weighted loss %s (%.0fs)" % (name, rr.mode, rr.loss, time.time() - t1), flush=True)
    if len(Da) <= DROP_MAX_MINIMAL:
        t1 = time.time()
        dr = drop(n, Da, w, time_limit=DROP_TIME, max_w=MAX_W, max_extra=max_extra_for(n), ascend_time=ASCEND_TIME)
        out["drop_w"] = {"exact": dr.exact, "heuristic": dr.heuristic, "lower_bound": dr.lower_bound,
                         "time": round(time.time() - t1, 1), "source": dr.stats.get("heuristic_source")}
        if dr.design is not None:
            designs["drop_w"] = dr.design
        print("%s: weighted Drop, weighted loss %s, exact %s (%.0fs)" % (name, dr.loss, dr.exact, time.time() - t1), flush=True)
    # the unit-weight designs of E1 and the weighted ones, on the same updates
    modes = {}
    for m in ["repair", "drop"]:
        d = rec0["designs"].get(m)
        if d:
            modes[m] = [(sum(1 << a for a in s["attrs"]), [sum(1 << a for a in K) for K in s["keys"]]) for s in d]
    for m, d in designs.items():
        ok = check_bcnf_design(n, d, Da)
        assert ok[0] and ok[1], (name, m, "not a sound and locally enforced BCNF design")
        modes[m] = d
    cache = {}
    for seed in seeds:
        upd_row, upd_attr, upd_val, mult = e4.draw_updates(codes, n, updates, seed)
        harmful = e4.violations(codes, mult, sigma, upd_row, upd_attr, upd_val).any(axis=1)
        cache[seed] = (upd_row, upd_attr, upd_val, mult, harmful)
    out["modes"] = {}
    for m, d in modes.items():
        E = key_dependencies(n, d)
        dj = design_json(n, Da, d)
        ev = risk_of(codes, n, sigma, dj, updates, seeds, cache)
        out["modes"][m] = {"loss": loss_of(Da, E), "weighted_loss": loss_of(Da, E, w), "schemata": len(d),
                           "risk": float(np.mean([x["risk"] for x in ev])), "seeds": ev, "design": dj}
        print("   %-8s loss %5d, weighted loss %7d, %4d schemata, risk %.3f" % (
            m, out["modes"][m]["loss"], out["modes"][m]["weighted_loss"], len(d), out["modes"][m]["risk"]), flush=True)
    out["time_total"] = round(time.time() - t0, 1)
    with open(os.path.join(ROOT, "results", "weighted_%s.jsonl" % name), "w", encoding="utf-8") as f:
        f.write(json.dumps(out) + "\n")

def table():
    for name in SETS:
        p = os.path.join(ROOT, "results", "weighted_%s.jsonl" % name)
        if not os.path.isfile(p):
            continue
        r = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()][-1]
        cells = ["%s loss %d wloss %d risk %.3f" % (m, v["loss"], v["weighted_loss"], v["risk"]) for m, v in r["modes"].items()]
        print("%-10s %s" % (name, " | ".join(cells)))

def main():
    args = sys.argv[1:]
    updates, wseeds, seeds, names = 10000, [6, 7, 8, 9, 10], [1, 2, 3, 4, 5], []
    i = 0
    while i < len(args):
        if args[i] == "--updates":
            updates = int(args[i + 1]); i += 2
        elif args[i] == "--wseeds":
            wseeds = [int(x) for x in args[i + 1].split(",")]; i += 2
        elif args[i] == "--seeds":
            seeds = [int(x) for x in args[i + 1].split(",")]; i += 2
        elif args[i] == "--budgets":
            drop_module.BUDGET_LIMIT = int(args[i + 1]); i += 2
        elif args[i] == "--table":
            table(); return
        else:
            names.append(args[i]); i += 1
    assert not set(wseeds) & set(seeds), "the weighting and evaluation seeds must be disjoint"
    for name in names:
        run(name, updates, wseeds, seeds)

if __name__ == "__main__":
    main()
