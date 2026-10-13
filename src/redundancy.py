r"""redundancy.py: the redundant data values and the storage of the designs of E3 (runs on the server).

Every design of E1 (results/e1_<name>.jsonl of experiments.py, with the greedy BCNF decomposition of gbcnf.py) stores
on each schema S the distinct projection r[S] of the source table src.<set> (pgload.py), as in E3. An occurrence t[A]
of a value in r[S] is redundant for Sigma iff some other tuple of r[S] agrees with t on Y for a minimal FD Y -> A of
Sigma with YA contained in S: every change of the value then violates Sigma[S] (Vincent's notion of redundancy for
FDs). A schema in BCNF for Sigma[S] holds no redundant value; the original relation and the critical schemata of 3NF
synthesis hold the copies that their non-key FDs determine, and a BCNF design holds those of the minimal FDs that it
leaves unenforced inside a schema.

The lookup-table designs of E3 (modes orig-f and 3nf-f of e3pg.py) add to the original relation and to iCONF one table
over XA per non-key FD X -> A of a minimal cover of every schema (the "fds" of the design); they keep the redundant
values of their base design and add the rows of the lookup tables, whose redundant values are counted in the same
way.

For every design the record holds the schemata, the stored rows and values (cells), and the redundant values.

usage: python3 redundancy.py [set ...]      results/redundancy_<set>.jsonl
       python3 redundancy.py --table
"""
import sys, os, json, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdlib import *
from e3 import SETS, e1_record, atomic
from e4 import load_table

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NAMES = ["abalone", "adult", "breast", "bridges", "echo", "hepatitis", "letter", "ncvoter", "weather"]
MODES = ["orig", "3nf", "3nfc", "bcnf", "gbcnf", "repair", "drop"]
LOOKUP = {"orig-f": "orig", "3nf-f": "3nf"}


def group_ids(codes, cols):
    """the id of the group of every row of codes on the columns cols (0 for every row if cols is empty)"""
    ids = np.zeros(codes.shape[0], dtype=np.int64)
    for c in cols:
        _, ids = np.unique(ids * (int(codes[:, c].max()) + 1) + codes[:, c], return_inverse=True)
        ids = ids.astype(np.int64)
    return ids


def projection(codes, S):
    """the distinct projection of codes onto the attribute list S, as a codes matrix of its own"""
    ids = group_ids(codes, S)
    _, first = np.unique(ids, return_index=True)
    return codes[np.sort(first)][:, S]


def schema_stats(codes, S, by_rhs):
    """(rows, cells, redundant values) of the distinct projection onto S"""
    proj = projection(codes, S)
    rows = proj.shape[0]
    pos = {a: i for i, a in enumerate(S)}
    mask_S = sum(1 << a for a in S)
    redundant = 0
    for A in S:
        red = np.zeros(rows, dtype=bool)
        for Y in by_rhs[A]:
            if Y & ~mask_S:
                continue
            ids = group_ids(proj, [pos[a] for a in bits(Y)])
            counts = np.bincount(ids)
            red |= counts[ids] >= 2
        redundant += int(red.sum())
    return rows, rows * len(S), redundant


def stats(codes, schemata, by_rhs):
    out = {"schemata": len(schemata), "rows": 0, "cells": 0, "redundant": 0}
    for S in schemata:
        r, c, d = schema_stats(codes, S, by_rhs)
        out["rows"] += r
        out["cells"] += c
        out["redundant"] += d
    return out


def run(name):
    t0 = time.time()
    rec = e1_record(name)
    n, Da = atomic(name)
    by_rhs = [[] for _ in range(n)]
    for Y, A in Da.fds:
        if Y:                       # no constant attribute is left (drop_constants.py)
            by_rhs[A].append(Y)
    codes = load_table(name)
    out = {"set": name, "records": int(codes.shape[0]), "attributes": n, "minimal_fds": len(Da), "designs": {}}
    for mode in MODES:
        d = rec["designs"].get(mode)
        if d is None:
            continue
        out["designs"][mode] = dict(loss=rec.get({"orig": "nu"}.get(mode, mode + "_loss")),
                                    **stats(codes, [sorted(s["attrs"]) for s in d], by_rhs))
        print("%s %-6s %s (%.0fs)" % (name, mode, out["designs"][mode], time.time() - t0), flush=True)
    for mode, base in LOOKUP.items():
        d = rec["designs"].get(base)
        if d is None or base not in out["designs"]:
            continue
        lookups = [sorted(set(X) | {A}) for s in d for X, A in (s.get("fds") or [])]
        lk = stats(codes, lookups, by_rhs)
        b = out["designs"][base]
        out["designs"][mode] = dict(loss=0, lookup_tables=lk["schemata"], lookup_rows=lk["rows"], lookup_cells=lk["cells"],
                                    lookup_redundant=lk["redundant"], schemata=b["schemata"] + lk["schemata"],
                                    rows=b["rows"] + lk["rows"], cells=b["cells"] + lk["cells"], redundant=b["redundant"] + lk["redundant"])
        print("%s %-6s %s (%.0fs)" % (name, mode, out["designs"][mode], time.time() - t0), flush=True)
    out["seconds"] = round(time.time() - t0, 1)
    with open(os.path.join(ROOT, "results", "redundancy_%s.jsonl" % name), "w", encoding="utf-8") as f:
        f.write(json.dumps(out) + "\n")


def table():
    cols = MODES + list(LOOKUP)
    print("%-10s %8s | %s" % ("set", "cells", " | ".join("%-21s" % m for m in cols)))
    for name in NAMES:
        f = os.path.join(ROOT, "results", "redundancy_%s.jsonl" % name)
        if not os.path.isfile(f):
            continue
        r = json.loads(open(f, encoding="utf-8").readline())
        orig = r["designs"]["orig"]["cells"]
        cells = []
        for m in cols:
            d = r["designs"].get(m)
            cells.append("%-21s" % ("--" if d is None else "red %d, x%.1f cells" % (d["redundant"], d["cells"] / orig)))
        print("%-10s %8d | %s" % (name, orig, " | ".join(cells)))


def main():
    args = sys.argv[1:]
    if args == ["--table"]:
        table()
        return
    for name in args or NAMES:
        run(name)


if __name__ == "__main__":
    main()
