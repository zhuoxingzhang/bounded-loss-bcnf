r"""stored_risk.py: the integrity risk of the designs of E4 when the updates run on the stored tables, and the risk
bound of Prop. "Risk bound".

The updates are those of e4.py (seeds 1 to 5, 10,000 each): attribute A of a random record t gets the value v of A
in another random record. Under the universal semantics of e4.py, the update is caught iff the updated relation
violates a declared key dependency. Under the stored semantics, every table of the design holds the distinct
projection of the data, and the update becomes, in every table whose schema contains A, the SQL UPDATE that sets A
to v in the row of t, identified by its first declared key; the transaction fails iff some UPDATE violates a unique
constraint, that is, iff for a declared key K of a table with A in K some stored row has the K-values of t with
A = v. A row is shared by all records with the same projection, so an UPDATE that succeeds changes the other
records with the projection of t as well (an update anomaly): a key K without A can no longer catch the update,
since the row keeps its K-values.

For every design and seed the record holds the harmful updates (those that violate Sigma), the missed ones under
both semantics (under the stored one also those that change no other record), the accepted updates that change
other records (anomalies), the number of other records they change in the table where most change (a lower bound on
the records changed) and summed over the tables (an upper bound), and the risk bound: the sum, over the minimal FDs that the design leaves unenforced, of the share of the
updates that violate the FD, which bounds the share of all updates that violate Sigma unnoticed under the universal
semantics (the share of the harmful updates, the integrity risk of E4, is the missed share over the harmful share).

usage: python src/stored_risk.py [--updates 10000] [--seeds 1,2,3,4,5] [set ...]      results/stored_<set>.jsonl
"""
import sys, os, json, time
import numpy as np
from fdlib import *
import experiments
from e3 import SETS, e1_record
import e4

MODES = ["keys", "3nf", "3nfc", "bcnf", "gbcnf", "repair", "drop", "repair_w", "drop_w"]


def designs_of(name, rec):
    out = {}
    for mode in MODES:
        if mode == "keys":
            d = rec["designs"].get("orig")
        elif mode.endswith("_w"):
            p = os.path.join(e4.ROOT, "results", "weighted_%s.jsonl" % name)
            w = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()][-1] if os.path.isfile(p) else None
            d = w["modes"][mode]["design"] if w and mode in w["modes"] else None
        else:
            d = rec["designs"].get(mode)
        if d:
            out[mode] = [(tuple(s["attrs"]), [tuple(K) for K in s["keys"]]) for s in d]
    return out


def stored(codes, mult, design, upd_row, upd_attr, upd_val):
    """(caught, most other records changed in one table, other records changed summed over the tables) per update
    under the stored semantics; nothing changes when the transaction fails"""
    N = len(upd_row)
    caught = np.zeros(N, dtype=bool)
    most = np.zeros(N, dtype=np.int64)
    total = np.zeros(N, dtype=np.int64)
    for S, keys in design:
        sel = np.nonzero(np.isin(upd_attr, S))[0]
        if not len(sel):
            continue
        rows = upd_row[sel]
        share = e4.FDIndex(codes, mult, S, S[0]).group_size(rows) - 1
        most[sel] = np.maximum(most[sel], share)
        total[sel] += share
        for K in keys:
            idx = None
            for a in K:
                s2 = sel[upd_attr[sel] == a]
                if not len(s2):
                    continue
                r2 = upd_row[s2]
                idx = idx or e4.FDIndex(codes, mult, K, K[0])
                h = idx.h[r2] + (upd_val[s2].astype(np.uint64) - codes[r2, a].astype(np.uint64)) * mult[a]
                exists, _ = idx.lookup(h, codes, lambda x, a=a, r2=r2, s2=s2: upd_val[s2] if x == a else codes[r2, x])
                caught[s2] |= exists
    most[caught] = 0
    total[caught] = 0
    return caught, most, total


def run(name, updates, seeds):
    rec = e1_record(name)
    n, F, _ = load_any(experiments.fd_path(SETS[name]))
    Da = FDSet(n, [(mask(X), A) for X, A in e4.tested_fds(n, F)[0]])
    assert len(Da) == rec["minimal_fds"], (name, len(Da), rec["minimal_fds"])
    sigma = [(tuple(bits(X)), A) for X, A in Da.fds]
    designs = designs_of(name, rec)
    lost = {}
    for mode, d in designs.items():
        E = key_dependencies(n, [(mask(S), [mask(K) for K in keys]) for S, keys in d])
        lost[mode] = np.array([not E.implies(X, A) for X, A in Da.fds])
    t0 = time.time()
    codes = e4.load_table(name)
    print("%s: %d rows, %d attributes, %d minimal FDs (%.0fs)" % (name, codes.shape[0], n, len(Da), time.time() - t0),
          flush=True)
    with open(os.path.join(e4.ROOT, "results", "stored_%s.jsonl" % name), "w", encoding="utf-8") as f:
        for seed in seeds:
            upd_row, upd_attr, upd_val, mult = e4.draw_updates(codes, n, updates, seed)
            V = e4.violations(codes, mult, sigma, upd_row, upd_attr, upd_val)
            harmful = V.any(axis=1)
            p = V.mean(axis=0)
            out = {"set": name, "seed": seed, "updates": updates, "harmful": int(harmful.sum()), "modes": {}}
            for mode, d in designs.items():
                t1 = time.time()
                kd = e4.key_dependencies_of([{"attrs": S, "keys": keys} for S, keys in d])
                cu = e4.violations(codes, mult, kd, upd_row, upd_attr, upd_val).any(axis=1)
                cs, most, total = stored(codes, mult, d, upd_row, upd_attr, upd_val)
                m = {"loss": int(lost[mode].sum()), "schemata": len(d),
                     "missed": int((harmful & ~cu).sum()), "missed_stored": int((harmful & ~cs).sum()),
                     "missed_stored_local": int((harmful & ~cs & (most == 0)).sum()),
                     "false_rejections": int((cu & ~harmful).sum()),
                     "false_rejections_stored": int((cs & ~harmful).sum()),
                     "anomalies": int((most > 0).sum()), "anomalies_harmless": int(((most > 0) & ~harmful).sum()),
                     "changed_most": int(most.sum()), "changed_total": int(total.sum()),
                     "risk_bound": float(p[lost[mode]].sum()), "time": round(time.time() - t1, 1)}
                assert m["missed"] <= m["risk_bound"] * updates + 1e-6, (name, mode, m)
                out["modes"][mode] = m
                print("   seed %d %-8s loss %5d | missed %5d, stored %5d (%5d local) of %d harmful | anomalies %5d, "
                      "%.1f records each | bound %.4f vs missed share %.4f" % (
                      seed, mode, m["loss"], m["missed"], m["missed_stored"], m["missed_stored_local"], out["harmful"],
                      m["anomalies"], m["changed_most"] / max(1, m["anomalies"]), m["risk_bound"], m["missed"] / updates),
                      flush=True)
            f.write(json.dumps(out) + "\n")
            f.flush()


def main():
    args = sys.argv[1:]
    updates, seeds, names = 10000, [1, 2, 3, 4, 5], []
    i = 0
    while i < len(args):
        if args[i] == "--updates":
            updates = int(args[i + 1]); i += 2
        elif args[i] == "--seeds":
            seeds = [int(x) for x in args[i + 1].split(",")]; i += 2
        else:
            names.append(args[i]); i += 1
    for name in names:
        run(name, updates, seeds)


if __name__ == "__main__":
    main()
