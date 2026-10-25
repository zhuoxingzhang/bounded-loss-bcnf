r"""worst_stored.py: the integrity risk on the stored tables (stored_risk.py) of the designs that the baselines and
Repair return over the orders of worst_case.py.

For every distinct design of a mode in results/worst_<set>.jsonl, the updates of e4.py (seeds 1 to 5) run on the
stored tables as in stored_risk.stored: an update is caught iff some declared key K of a table contains the updated
attribute and some stored row has the K-values of the updated record, and an update that is not caught changes the
other records that share its row in a table containing the updated attribute. Both tests depend only on K and on the
schema, so they are computed once per key and per schema and shared by all designs. Run 0 reproduces the record of
stored_risk.py (the record says whether it does).

The record of a set holds, per mode, the missed harmful updates per seed of every distinct design, all of them (stored)
and those that change no other record (local), as in stored_risk.py; a later call with other modes adds them.

usage: python3 worst_stored.py [--modes 3nf,bcnf,repair] [set ...]      results/worst_stored_<set>.jsonl
       python3 worst_stored.py --table
"""
import sys, os, json, time
import numpy as np

from fdlib import *
import experiments
from e3 import SETS
import e4

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODES = ["3nf", "bcnf"]

def run(name, modes):
    w = json.loads(open(os.path.join(ROOT, "results", "worst_%s.jsonl" % name), encoding="utf-8").readline())
    n, F, _ = load_any(experiments.fd_path(SETS[name]))
    sigma = e4.tested_fds(n, F)[0]
    designs = {m: [[(tuple(s["attrs"]), [tuple(K) for K in s["keys"]]) for s in d["design"]] for d in w["modes"][m]["designs"]]
               for m in modes}
    schemata = sorted({S for m in modes for d in designs[m] for S, _ in d})
    keys = sorted({K for m in modes for d in designs[m] for _, ks in d for K in ks})
    t0 = time.time()
    codes = e4.load_table(name)
    print("%s: %d rows, %s designs, %d schemata, %d keys (%.0fs)" % (name, codes.shape[0], ", ".join(
        "%s %d" % (m, len(designs[m])) for m in modes), len(schemata), len(keys), time.time() - t0), flush=True)
    out = {"set": name, "updates": w["updates"], "seeds": w["seeds"], "harmful": [], "modes": {
        m: [{"runs": d["runs"], "missed_stored": [], "missed_stored_local": []} for d in w["modes"][m]["designs"]] for m in modes}}
    for seed in w["seeds"]:
        t1 = time.time()
        upd_row, upd_attr, upd_val, mult = e4.draw_updates(codes, n, w["updates"], seed)
        harmful = e4.violations(codes, mult, sigma, upd_row, upd_attr, upd_val).any(axis=1)
        out["harmful"].append(int(harmful.sum()))
        # per schema S: the other records that share the row of the updated record, for the updates of an attribute of S
        share = {}
        for S in schemata:
            v = np.zeros(len(upd_row), dtype=np.int64)
            sel = np.nonzero(np.isin(upd_attr, S))[0]
            if len(sel):
                v[sel] = e4.FDIndex(codes, mult, S, S[0]).group_size(upd_row[sel]) - 1
            share[S] = v
        # per key K: the updates of an attribute of K whose new K-values some stored row has
        caught_by = {}
        for K in keys:
            c = np.zeros(len(upd_row), dtype=bool)
            idx = None
            for a in K:
                s2 = np.nonzero(upd_attr == a)[0]
                if not len(s2):
                    continue
                r2 = upd_row[s2]
                idx = idx or e4.FDIndex(codes, mult, K, K[0])
                h = idx.h[r2] + (upd_val[s2].astype(np.uint64) - codes[r2, a].astype(np.uint64)) * mult[a]
                exists, _ = idx.lookup(h, codes, lambda x, a=a, r2=r2, s2=s2: upd_val[s2] if x == a else codes[r2, x])
                c[s2] |= exists
            caught_by[K] = c
        for m in modes:
            for d, o in zip(designs[m], out["modes"][m]):
                caught = np.zeros(len(upd_row), dtype=bool)
                most = np.zeros(len(upd_row), dtype=np.int64)
                for S, ks in d:
                    most = np.maximum(most, share[S])
                    for K in ks:
                        caught |= caught_by[K]
                missed = harmful & ~caught
                o["missed_stored"].append(int(missed.sum()))
                o["missed_stored_local"].append(int((missed & (most == 0)).sum()))
        print("   %s seed %d: %d harmful (%.0fs)" % (name, seed, harmful.sum(), time.time() - t1), flush=True)
    # run 0 against stored_risk.py
    s = [json.loads(l) for l in open(os.path.join(ROOT, "results", "stored_%s.jsonl" % name), encoding="utf-8") if l.strip()]
    for m in modes:
        o = out["modes"][m][0]
        assert o["runs"][0] == 0
        o["e1"] = all(r["harmful"] == h and r["modes"][m]["missed_stored"] == a and r["modes"][m]["missed_stored_local"] == b
                      for r, h, a, b in zip(s, out["harmful"], o["missed_stored"], o["missed_stored_local"]))
    path = os.path.join(ROOT, "results", "worst_stored_%s.jsonl" % name)
    if os.path.isfile(path):   # keep the modes of an earlier run on the same updates
        old = json.loads(open(path, encoding="utf-8").readline())
        if (old["updates"], old["seeds"], old["harmful"]) == (out["updates"], out["seeds"], out["harmful"]):
            out["modes"] = {**old["modes"], **out["modes"]}
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(out) + "\n")
    for m in modes:
        risks = [100 * np.mean(np.array(d["missed_stored"]) / out["harmful"]) for d in out["modes"][m]]
        print("   %-5s run 0 %s | stored risk %.1f to %.1f%% over %d designs" % (
            m, "= stored_risk.py" if out["modes"][m][0]["e1"] else "DIFFERS from stored_risk.py", min(risks), max(risks), len(risks)), flush=True)

def worst(r, m):
    """the design of mode m with the highest risk on the stored tables, for Repair the one with the lowest: (viol.,
    anom.) in per cent of the harmful updates, means over the seeds"""
    h = np.array(r["harmful"])
    d = (min if m == "repair" else max)(r["modes"][m], key=lambda d: np.mean(np.array(d["missed_stored"]) / h))
    viol = 100 * np.mean(np.array(d["missed_stored_local"]) / h)
    return viol, 100 * np.mean(np.array(d["missed_stored"]) / h) - viol

def table():
    for name in SETS:
        f = os.path.join(ROOT, "results", "worst_stored_%s.jsonl" % name)
        if os.path.isfile(f):
            r = json.loads(open(f, encoding="utf-8").readline())
            print("%-10s %s" % (name, "  ".join("%s %.1f + %.1f" % ((m,) + worst(r, m)) for m in r["modes"])))

def main():
    args = sys.argv[1:]
    modes, names = MODES, []
    i = 0
    while i < len(args):
        if args[i] == "--modes":
            modes = args[i + 1].split(","); i += 2
        elif args[i] == "--table":
            table(); return
        else:
            names.append(args[i]); i += 1
    for name in names:
        run(name, modes)

if __name__ == "__main__":
    main()
