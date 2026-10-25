r"""teaser_risk.py: the integrity risk of the designs of the running example (the teaser of the paper), on the address
book of teaser.py (World) with `base` customers at random addresses among the 50 streets of each of the 200 towns, as
in teaser_pg.py.

The updates, the harmful updates and the two semantics are those of stored_risk.py: attribute A of a random record
gets the value of A in another random record; under the universal semantics the update is caught iff the updated
relation violates an enforced dependency, and under the stored semantics iff some SQL UPDATE of the row of the
record in a table that contains A violates a constraint of the table. D5 adds to D4 the exclusion constraint for
Z -> T on STZ. Under the stored semantics, it rejects the new value of T iff another row of STZ has the zip code of
the record, and the new value of Z iff a row with that zip code has another town.

  D1  CSTZ (key C)                          loss 2
  D2  ZT (Z), CSZ (C)                       loss 1
  D4  STZ (ST, SZ), CST (C)                 loss 1
  D5  D4 with Z -> T as exclusion constraint  loss 0

usage: python src/teaser_risk.py [--base 100000] [--updates 10000] [--seeds 1,2,3,4,5]       results/teaser_risk.jsonl
"""
import sys, os, json, random
import numpy as np
from fdlib import *
from teaser import World
import e4
from stored_risk import stored

C, S, T, Z = range(4)
SIGMA = FDSet(4, [(mask([C]), S), (mask([C]), T), (mask([S, T]), Z), (mask([Z]), T)])
# name: (list of (schema, keys), exclusion constraints (table index, X, B))
DESIGNS = {
    "D1": ([((C, S, T, Z), [(C,)])], []),
    "D2": ([((T, Z), [(Z,)]), ((C, S, Z), [(C,)])], []),
    "D4": ([((S, T, Z), [(S, T), (S, Z)]), ((C, S, T), [(C,)])], []),
    "D5": ([((S, T, Z), [(S, T), (S, Z)]), ((C, S, T), [(C,)])], [(0, (Z,), T)]),
}


def coded(rows):
    """the rows as value codes per attribute, in the sorted order of the values"""
    codes = np.empty((len(rows), 4), dtype=np.int64)
    for a in range(4):
        values, codes[:, a] = np.unique([r[a] for r in rows], return_inverse=True)
    return codes


def excluded(codes, mult, design, X, B, upd_row, upd_attr, upd_val, j):
    """the updates that the exclusion constraint X -> B on table j rejects under the stored semantics"""
    Sj = design[j][0]
    out = np.zeros(len(upd_row), dtype=bool)
    idx = e4.FDIndex(codes, mult, X, B)
    sel = np.nonzero(upd_attr == B)[0]
    if len(sel):   # another row of the table has the X-values of the record
        rows = upd_row[sel]
        out[sel] = idx.group_size(rows) > e4.FDIndex(codes, mult, Sj, Sj[0]).group_size(rows)
    for a in X:   # a row with the new X-values has another B-value
        sel = np.nonzero(upd_attr == a)[0]
        if not len(sel):
            continue
        rows = upd_row[sel]
        h = idx.h[rows] + (upd_val[sel].astype(np.uint64) - codes[rows, a].astype(np.uint64)) * mult[a]
        exists, b = idx.lookup(h, codes, lambda x, a=a, rows=rows, sel=sel: upd_val[sel] if x == a else codes[rows, x])
        out[sel] = exists & (b != codes[rows, B])
    return out


def run(base, updates, seeds):
    Da = atomic_cover(SIGMA)
    sigma = [(tuple(bits(X)), A) for X, A in Da.fds]
    out = open(os.path.join(e4.ROOT, "results", "teaser_risk.jsonl"), "a", encoding="utf-8")
    for seed in seeds:
        codes = coded(World(random.Random(seed)).customers(base, 0, fresh_share=0))
        upd_row, upd_attr, upd_val, mult = e4.draw_updates(codes, 4, updates, seed)
        V = e4.violations(codes, mult, sigma, upd_row, upd_attr, upd_val)
        harmful = V.any(axis=1)
        rec = {"seed": seed, "base": base, "updates": updates, "harmful": int(harmful.sum()), "designs": {}}
        for name, (design, excl) in DESIGNS.items():
            E = key_dependencies(4, [(mask(Sch), [mask(K) for K in keys]) for Sch, keys in design])
            E = FDSet(4, E.fds + [(mask(X), B) for _, X, B in excl])
            lost = [not E.implies(X, A) for X, A in Da.fds]
            kd = e4.key_dependencies_of([{"attrs": Sch, "keys": keys} for Sch, keys in design])
            cu = e4.violations(codes, mult, kd + [(X, B) for _, X, B in excl], upd_row, upd_attr, upd_val).any(axis=1)
            cs, most, total = stored(codes, mult, design, upd_row, upd_attr, upd_val)
            for j, X, B in excl:
                hit = excluded(codes, mult, design, X, B, upd_row, upd_attr, upd_val, j) & ~cs
                cs |= hit
                most[hit] = 0
                total[hit] = 0
            m = {"loss": int(sum(lost)), "schemata": len(design),
                 "missed": int((harmful & ~cu).sum()), "missed_stored": int((harmful & ~cs).sum()),
                 "missed_stored_local": int((harmful & ~cs & (most == 0)).sum()),
                 "false_rejections": int((cu & ~harmful).sum()),
                 "false_rejections_stored": int((cs & ~harmful).sum()),
                 "anomalies": int((most > 0).sum()), "changed_most": int(most.sum()), "changed_total": int(total.sum())}
            m["risk"] = m["missed"] / max(1, rec["harmful"])
            m["risk_stored"] = m["missed_stored"] / max(1, rec["harmful"])
            rec["designs"][name] = m
            print("seed %d %s loss %d | missed %5d, stored %5d (%5d local) of %d harmful | anomalies %5d" % (
                seed, name, m["loss"], m["missed"], m["missed_stored"], m["missed_stored_local"], rec["harmful"],
                m["anomalies"]), flush=True)
        out.write(json.dumps(rec) + "\n")
        out.flush()
    out.close()


def main():
    args = sys.argv[1:]
    base, updates, seeds = 100000, 10000, [1, 2, 3, 4, 5]
    i = 0
    while i < len(args):
        if args[i] == "--base":
            base = int(args[i + 1]); i += 2
        elif args[i] == "--updates":
            updates = int(args[i + 1]); i += 2
        elif args[i] == "--seeds":
            seeds = [int(x) for x in args[i + 1].split(",")]; i += 2
        else:
            i += 1
    run(base, updates, seeds)


if __name__ == "__main__":
    main()
