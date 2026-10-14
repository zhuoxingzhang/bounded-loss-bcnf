r"""syn_compare.py: the classical 3NF synthesis of the experiments (Bernstein's synthesis, fdlib.synthesize_3nf)
against the 3NF synthesis DecompAlg4 that the experiments of the iCONF paper compare iCONF with (iconf.decomp4), on
one FD set of E1 (runs on the server).

For both designs, with all minimal keys declared: the number of schemata, the critical schemata (not in BCNF), the
loss (minimal FDs not implied by the key dependencies) and the exclusion constraints that E3 declares (the non-key
FDs of a minimal cover of every schema, experiments.design_json). The Bernstein design and the iCONF design come from
the E1 record (results/e1_<set>.jsonl); DecompAlg4 runs on the atomic cover Sigma_a of E1, in its order.
With --java, the Java implementation (iconf/Decomp4Driver.java) runs as well and must return the same schemata.
With --risk, on the sets of E3 and E4 (e3.SETS), the integrity risk of DecompAlg4 with its keys only is measured on
the updates of E4 (seeds 1 to 5, e4.py) and set beside the risks of the E4 record.

usage: python3 syn_compare.py [--java] [--risk] <E1 set> ...      results/syn_compare_<set>.json
       python3 syn_compare.py --table
"""
import sys, os, json, time, glob, subprocess
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdlib import *
import experiments
from iconf import decomp4, decomp4_java

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
JAVA_TIMEOUT = 3600   # seconds for the Java implementation

def sigma_a(n, F):
    """the atomic cover of E1 (experiments.run)"""
    if len(F) > experiments.ASSUME_ATOMIC_ABOVE and all(not any(F.implies(X & ~(1 << a), A) for a in bits(X)) for (X, A) in F.fds):
        return FDSet(n, sorted(set(F.fds)))
    return atomic_cover(F, cap=experiments.MAX_MINIMAL)

def exclusion(design):
    fds = [s.get("fds") for s in design]
    return None if any(f is None for f in fds) else sum(len(f) for f in fds)

def risk(name, design, n, F, seeds=(1, 2, 3, 4, 5), updates=10000):
    """the mean integrity risk (per cent) of a design with its keys only on the updates of E4, and the risks of the
    E4 record by mode"""
    import e3, e4
    e3name = next(k for k, v in e3.SETS.items() if v == name)
    codes = e4.load_table(e3name)
    sigma, _ = e4.tested_fds(n, F)
    kd = e4.key_dependencies_of(design)
    risks = []
    for seed in seeds:
        upd_row, upd_attr, upd_val, mult = e4.draw_updates(codes, n, updates, seed)
        harmful = e4.violations(codes, mult, sigma, upd_row, upd_attr, upd_val).any(axis=1)
        caught = e4.violations(codes, mult, kd, upd_row, upd_attr, upd_val).any(axis=1)
        risks.append(100.0 * (harmful & ~caught).sum() / harmful.sum() if harmful.sum() else 0.0)
    recs = [json.loads(l) for l in open(os.path.join(ROOT, "results", "e4_%s.jsonl" % e3name), encoding="utf-8") if l.strip()]
    stored = {m: 100.0 * float(np.mean([r["modes"][m]["risk"] for r in recs])) for m in ("3nf", "3nfc") if m in recs[0]["modes"]}
    return float(np.mean(risks)), stored

def run(name, java=False, with_risk=False):
    n, F, _ = load_any(experiments.fd_path(name))
    Da = sigma_a(n, F)
    rec = [json.loads(l) for l in open(os.path.join(ROOT, "results", "e1_%s.jsonl" % experiments.safe(name)), encoding="utf-8") if l.strip()][-1]
    out = {"set": name, "n": n, "minimal_fds": len(Da)}
    for mode in ("3nf", "3nfc"):
        d = rec["designs"][mode]
        out[mode] = {"schemata": len(d), "loss": rec[mode + "_loss"], "exclusion": exclusion(d),
                     "critical": sum(1 for s in d if not is_bcnf(Da, sum(1 << a for a in s["attrs"])))}
    t = time.time()
    dec = decomp4(n, Da)
    des = keyed(Da, dec)
    d = experiments.design_json(n, Da, des, triggers=True)
    out["decomp4"] = {"schemata": len(dec), "loss": loss_of(Da, key_dependencies(n, des)), "exclusion": exclusion(d),
                      "critical": sum(1 for S in dec if not is_bcnf(Da, S)), "time": round(time.time() - t, 1)}
    if java:
        try:
            dj, tj = decomp4_java(n, Da, timeout=JAVA_TIMEOUT)
            out["decomp4"]["java_same"] = set(dj) == set(dec)
            out["decomp4"]["java_time"] = tj
        except subprocess.TimeoutExpired:
            out["decomp4"]["java_same"] = "timeout"
    if with_risk:
        r, stored = risk(name, d, n, F)
        out["decomp4"]["risk"] = r
        for m, v in stored.items():
            out[m]["risk"] = v
    out["decomp4_design"] = d
    with open(os.path.join(ROOT, "results", "syn_compare_%s.json" % experiments.safe(name)), "w", encoding="utf-8") as f:
        f.write(json.dumps(out) + "\n")
    print(line(out), flush=True)

def line(r):
    def cell(m):
        x = r[m]
        s = "%4d sch %3d crit loss %5s excl %5s" % (x["schemata"], x["critical"], x["loss"], x["exclusion"])
        return s + (" risk %6.2f" % x["risk"] if "risk" in x else "")
    same = r["decomp4"].get("java_same")
    return "%-22s |Da| %6d | iConf %s | Bernstein %s | DecompAlg4 %s%s" % (
        r["set"], r["minimal_fds"], cell("3nf"), cell("3nfc"), cell("decomp4"), "" if same is None else " java same %s" % same)

def table():
    for p in sorted(glob.glob(os.path.join(ROOT, "results", "syn_compare_*.json"))):
        print(line(json.loads(open(p, encoding="utf-8").read())))

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--table" in args:
        table()
    else:
        names = [a for a in args if not a.startswith("--")]
        for name in names:
            run(name, java="--java" in args, with_risk="--risk" in args)
