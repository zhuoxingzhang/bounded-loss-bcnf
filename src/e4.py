r"""e4.py: integrity risk of the unenforced FDs under random updates (experiment E4; runs on the server).

For a data set, `updates` random single-attribute updates are drawn: a random stored record, a random attribute
A, and a new value for A taken from another random record (so that the value exists in the domain of A).
Every update is evaluated on its own against the stored relation (the source table src.<set> in PostgreSQL,
pgload.py, which holds the same rows as the table e3.<set> of e3load.py in MySQL):
it is harmful if the updated relation violates some FD of Sigma (tested on the atomic cover, or on the discovered
cover when the atomic cover is large), and a design catches it if the updated relation violates one of the key
dependencies the design declares (a relation satisfies the enforced FDs iff it satisfies the declared key
dependencies). The designs are those of E1 (results/e1_<name>.jsonl of experiments.py): the original relation
with its keys only, iCONF and the classical 3NF synthesis with their keys only (the non-key FDs left to the
application), classical and greedy BCNF (gbcnf.py), Repair and Drop. The integrity risk of a design is the share of harmful updates it
does not catch. Every seed draws its own updates; the record of a set holds one line per seed.

An update of attribute A of record t to the value v violates X -> B with A = B iff another record agrees with t
on X (the stored relation satisfies the FD, so the group of t agrees on B), and with A in X iff a stored record
agrees with the updated t on X and differs on B. Both tests use a sorted hash of the X-values per FD.

usage: python3 e4.py [--updates 10000] [--seeds 1,2,3,4,5] [set ...]      results/e4_<set>.jsonl
       python3 e4.py --table
"""
import sys, os, json, time, random
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdlib import *
import experiments
from e3 import SETS, e1_record
from pgdb import connect, qi

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)   # the repository root, which holds data/, results/ and iconf/
MAX_ATOMIC = 10000
MODES = ["keys", "3nf", "3nfc", "bcnf", "gbcnf", "repair", "drop"]

def load_table(name):
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='src' AND table_name=%s", (name,))
    cols = ["c%d" % j for j in experiments.source_columns(SETS[name], cur.fetchone()[0])]   # the columns of the attributes
    n = len(cols)
    cur.execute("SELECT %s FROM src.%s" % (", ".join(cols), qi(name)))
    rows = cur.fetchall()
    con.close()
    codes = np.empty((len(rows), n), dtype=np.int64)
    for a in range(n):
        _, inv = np.unique(np.array([r[a] for r in rows], dtype=object), return_inverse=True)
        codes[:, a] = inv
    return codes

class FDIndex:
    """sorted hash of the X-values of the stored rows for one FD X -> B"""
    def __init__(self, codes, mult, X, B):
        self.X, self.B = X, B
        h = np.zeros(codes.shape[0], dtype=np.uint64)
        for a in X:
            h += codes[:, a].astype(np.uint64) * mult[a]
        self.h = h
        self.order = np.argsort(h, kind="stable")
        self.sorted = h[self.order]
        self.bvals = codes[self.order, B]
        self.left = np.searchsorted(self.sorted, h, side="left")
        self.right = np.searchsorted(self.sorted, h, side="right")

    def group_size(self, rows):
        return self.right[rows] - self.left[rows]

    def lookup(self, hashes, codes, newcodes_fn):
        """for every query hash: (exists, B value of the group) with an exact check of the X-values"""
        idx = np.searchsorted(self.sorted, hashes, side="left")
        idx = np.minimum(idx, len(self.sorted) - 1)
        exists = self.sorted[idx] == hashes
        row = self.order[idx]
        # verify the X-values (hash collisions)
        if exists.any():
            same = np.ones(len(hashes), dtype=bool)
            for a in self.X:
                same &= codes[row, a] == newcodes_fn(a)
            exists &= same
        return exists, self.bvals[idx]

def violations(codes, mult, fds, upd_row, upd_attr, upd_val, verbose_label=None):
    """for a list of FDs (X, B) with attribute indices: a boolean matrix (updates x fds) of violations"""
    N = len(upd_row)
    out = np.zeros((N, len(fds)), dtype=bool)
    t0 = time.time()
    for j, (X, B) in enumerate(fds):
        idx = FDIndex(codes, mult, X, B)
        # A = B: the old X-group of the row has at least one other member
        sel = np.nonzero(upd_attr == B)[0]
        if len(sel):
            out[sel, j] = idx.group_size(upd_row[sel]) >= 2
        # A in X: the updated X-values hit a stored group whose B differs from the row's B
        for a in X:
            sel = np.nonzero(upd_attr == a)[0]
            if not len(sel):
                continue
            rows = upd_row[sel]
            h = idx.h[rows] + (upd_val[sel].astype(np.uint64) - codes[rows, a].astype(np.uint64)) * mult[a]
            def newcodes(x, a=a, rows=rows, sel=sel):
                return upd_val[sel] if x == a else codes[rows, x]
            exists, b = idx.lookup(h, codes, newcodes)
            out[sel, j] = exists & (b != codes[rows, B])
        if verbose_label and (j + 1) % 500 == 0:
            print("   %s: %d/%d FDs (%.0fs)" % (verbose_label, j + 1, len(fds), time.time() - t0), flush=True)
    return out

def key_dependencies_of(design):
    fds = []
    for s in design:
        S = set(s["attrs"])
        for K in s["keys"]:
            for b in sorted(S - set(K)):
                fds.append((tuple(K), b))
    return sorted(set(fds))

def run(name, updates, seeds):
    rec = e1_record(name)
    path = dict(experiments.SETS)[SETS[name]]
    n, F, _ = load_any(path)
    t0 = time.time()
    codes = load_table(name)
    rows = codes.shape[0]
    print("%s: %d rows, %d attributes loaded (%.0fs)" % (name, rows, n, time.time() - t0), flush=True)
    with open(os.path.join(ROOT, "results", "e4_%s.jsonl" % name), "w", encoding="utf-8") as f:
        for seed in seeds:
            f.write(json.dumps(run_seed(name, rec, n, F, codes, updates, seed)) + "\n")
            f.flush()

def draw_updates(codes, n, updates, seed):
    """the random updates of a seed (row, attribute, new value code) and the hash multipliers of the FD indexes"""
    rows = codes.shape[0]
    rng = np.random.default_rng(seed)
    nonconst = [a for a in range(n) if codes[:, a].max() > 0]
    upd_row = rng.integers(0, rows, size=updates)
    upd_attr = rng.choice(nonconst, size=updates)
    upd_val = np.empty(updates, dtype=np.int64)
    for i in range(updates):
        a = upd_attr[i]
        v = codes[rng.integers(0, rows), a]
        while v == codes[upd_row[i], a]:
            v = codes[rng.integers(0, rows), a]
        upd_val[i] = v
    mult = (rng.integers(1, 2**63 - 1, size=n, dtype=np.int64).astype(np.uint64) * np.uint64(2) + np.uint64(1))
    return upd_row, upd_attr, upd_val, mult

def run_seed(name, rec, n, F, codes, updates, seed):
    rows = codes.shape[0]
    # the FDs of Sigma to test: the atomic cover when it is small, else the discovered cover
    if len(F) <= experiments.ASSUME_ATOMIC_ABOVE:
        Da = atomic_cover(F, cap=experiments.MAX_MINIMAL)
    else:
        Da = FDSet(n, sorted(set(F.fds)))
    if len(Da) <= MAX_ATOMIC:
        sigma = [(tuple(bits(X)), A) for (X, A) in Da.fds]
        cover = "atomic"
    else:
        sigma = sorted(set((tuple(bits(X)), A) for (X, A) in F.fds))
        cover = "discovered"
    upd_row, upd_attr, upd_val, mult = draw_updates(codes, n, updates, seed)
    t1 = time.time()
    V = violations(codes, mult, sigma, upd_row, upd_attr, upd_val, verbose_label=name + " Sigma")
    harmful = V.any(axis=1)
    out = {"set": name, "rows": rows, "attributes": n, "updates": updates, "seed": seed, "cover": cover, "fds_tested": len(sigma),
           "harmful": int(harmful.sum()), "time_sigma": round(time.time() - t1, 1), "modes": {}}
    print("%s: %d of %d updates violate Sigma (%s cover, %d FDs, %.0fs)" % (name, harmful.sum(), updates, cover, len(sigma), time.time() - t1), flush=True)
    designs = rec["designs"]
    for mode in MODES:
        if mode == "keys":
            d = [dict(attrs=s["attrs"], keys=s["keys"]) for s in designs.get("orig", [])]
        else:
            d = designs.get(mode)
        if not d:
            continue
        kd = key_dependencies_of(d)
        t1 = time.time()
        C = violations(codes, mult, kd, upd_row, upd_attr, upd_val)
        caught = C.any(axis=1)
        missed = harmful & ~caught
        # which minimal FDs of Sigma do the missed updates violate? (the unenforced ones, by construction)
        per_fd = V[missed].sum(axis=0) if missed.any() else np.zeros(len(sigma), dtype=int)
        top = sorted(((int(per_fd[j]), "%s -> %d" % (",".join(map(str, sigma[j][0])), sigma[j][1])) for j in range(len(sigma)) if per_fd[j] > 0), reverse=True)[:10]
        loss = {"keys": rec.get("nu"), "3nf": rec.get("3nf_loss"), "3nfc": rec.get("3nfc_loss"), "bcnf": rec.get("bcnf_loss"),
                "gbcnf": rec.get("gbcnf_loss"), "repair": rec.get("repair_loss"), "drop": rec.get("drop_loss")}[mode]
        m = {"loss": loss, "schemata": len(d), "key_dependencies": len(kd), "caught": int((harmful & caught).sum()),
             "missed": int(missed.sum()), "risk": (float(missed.sum() / harmful.sum()) if harmful.sum() else 0.0),
             "false_rejections": int((caught & ~harmful).sum()), "violated_unenforced_fds": int((per_fd > 0).sum()), "top": top,
             "time": round(time.time() - t1, 1)}
        out["modes"][mode] = m
        print("   %-7s loss %5s | %4d schemata, %5d key deps | caught %5d, missed %5d, risk %.3f, false rejections %d (%.0fs)" % (
            mode, loss, len(d), len(kd), m["caught"], m["missed"], m["risk"], m["false_rejections"], m["time"]), flush=True)
    return out

def table():
    for name in SETS:
        f = os.path.join(ROOT, "results", "e4_%s.jsonl" % name)
        if not os.path.isfile(f):
            continue
        rs = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
        r = rs[0]
        cells = []
        for m in MODES:
            xs = [x["modes"][m]["risk"] for x in rs if m in x["modes"]]
            if xs:
                cells.append("%s %.3f+-%.3f" % (m, float(np.mean(xs)), float(np.std(xs, ddof=1)) if len(xs) > 1 else 0.0))
        print("%-12s %7d rows, %d FDs (%s), harmful %s/%d over %d seeds | %s" % (name, r["rows"], r["fds_tested"], r["cover"],
              "/".join(str(x["harmful"]) for x in rs), r["updates"], len(rs), "  ".join(cells)))

def main():
    args = sys.argv[1:]
    updates, seeds, names = 10000, [1, 2, 3, 4, 5], []
    i = 0
    while i < len(args):
        if args[i] == "--updates":
            updates = int(args[i + 1]); i += 2
        elif args[i] == "--seeds":
            seeds = [int(x) for x in args[i + 1].split(",")]; i += 2
        elif args[i] == "--table":
            table(); return
        else:
            names.append(args[i]); i += 1
    for name in names or list(SETS):
        run(name, updates, seeds)

if __name__ == "__main__":
    main()
