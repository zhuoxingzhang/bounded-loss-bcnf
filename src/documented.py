r"""documented.py: the data of three documented FD sets of meaningful.py for E3 and E4 (runs on the server).

The downloads are not part of the repository (sources in the README):
  data/documented/food/rows.csv          City of Chicago, Food Inspections (data.cityofchicago.org, 4ijn-s7e5)
  data/documented/pricepaid/pp-2024.csv  HM Land Registry, Price Paid Data, the transactions of 2024
  data/documented/hospital/clean.csv     the clean hospital data of Raha (BigDaMa/raha, datasets/hospital)

For every set the script reads the records in the attribute order of the FD set, trims every value, collapses runs
of white space, writes letters in upper case and the empty value as '?', and removes duplicate records. It then
removes, until every FD of the set holds, the records whose right-hand side value differs from the most frequent one
of their left-hand side value (a greedy subset repair, FD by FD in the order of the set). The remaining records go to
the table src.<set> of PostgreSQL (pgdb.py; every column text, named c0 .. c(n-1) as in pgload.py), and the designs
of the documented set (results/meaningful_<set>.jsonl) go to results/e1_doc-<set>.jsonl in the format of
experiments.py, so that e3pg.py, e4.py and weighted.py run on them unchanged.

usage: python3 documented.py --clean [set ...]     clean the downloads (results/documented_<set>.json: the counts)
       python3 documented.py --load [set ...]      clean and load the records into src.<set>
       python3 documented.py --designs [set ...]   write results/e1_doc-<FD set>.jsonl
"""
import sys, os, io, csv, json, re, time
from collections import Counter, defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdlib import *
import meaningful
from experiments import design_json, safe, MAX_MINIMAL

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data", "documented")
csv.field_size_limit(1 << 30)

# E3 name: (FD set of meaningful.py, download, header line, columns to skip)
SETS = {"food": ("food+c1", "food/rows.csv", True, []),
        "pricepaid": ("uk", "pricepaid/pp-2024.csv", False, []),
        "hospital": ("hospital", "hospital/clean.csv", True, [0])}   # column 0 of the hospital data is a row number

def e1_name(name):
    return "doc-" + SETS[name][0]

WS = re.compile(r"\s+")

def norm(v):
    v = WS.sub(" ", v).strip().upper()
    return v if v else "?"

def read(name):
    mset, path, header, skip = SETS[name]
    names, _ = meaningful.SETS[mset]
    rows = []
    with open(os.path.join(DATA, path), encoding="utf-8", newline="") as f:
        r = csv.reader(f)
        if header:
            next(r)
        for rec in r:
            rec = [v for j, v in enumerate(rec) if j not in skip]
            assert len(rec) == len(names), (name, len(rec), rec[:3])
            rows.append(tuple(norm(v) for v in rec))
    return names, rows

def fd_list(mset):
    names, fds = meaningful.SETS[mset]
    idx = {a: i for i, a in enumerate(names)}
    return [(tuple(idx[a] for a in lhs), idx[b]) for lhs, rhs in fds for b in rhs if b not in lhs]

def subset_repair(rows, fds, names):
    """the indices of the records kept; per FD the records it removed"""
    alive = list(range(len(rows)))
    removed = Counter()
    changed = True
    while changed:
        changed = False
        for X, A in fds:
            groups = defaultdict(Counter)
            for i in alive:
                groups[tuple(rows[i][x] for x in X)][rows[i][A]] += 1
            keep = {k: min(c.items(), key=lambda t: (-t[1], t[0]))[0] for k, c in groups.items() if len(c) > 1}
            if not keep:
                continue
            new = [i for i in alive if keep.get(tuple(rows[i][x] for x in X), rows[i][A]) == rows[i][A]]
            removed[",".join(names[x] for x in X) + "->" + names[A]] += len(alive) - len(new)
            alive = new
            changed = True
    return alive, removed

def clean(name):
    t0 = time.time()
    mset = SETS[name][0]
    names, rows = read(name)
    read_rows = len(rows)
    rows = list(dict.fromkeys(rows))
    alive, removed = subset_repair(rows, fd_list(mset), names)
    kept = [rows[i] for i in alive]
    stats = {"set": name, "fd_set": mset, "records": read_rows, "duplicates": read_rows - len(rows), "kept": len(kept),
             "removed_per_fd": dict(removed.most_common()),
             "distinct": {a: len(set(r[j] for r in kept)) for j, a in enumerate(names)},
             "time": round(time.time() - t0, 1)}
    with open(os.path.join(ROOT, "results", "documented_%s.json" % name), "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=1)
    print("%s: %d records, %d duplicates, %d kept (%.1f%%), removed by %s (%.0fs)" % (
        name, read_rows, stats["duplicates"], len(kept), 100.0 * len(kept) / read_rows,
        dict(removed.most_common(6)), stats["time"]), flush=True)
    return names, kept

def esc(v):
    return v.replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")

def load(name, chunk=100000):
    from pgdb import connect, qi
    names, kept = clean(name)
    t0 = time.time()
    cols = ["c%d" % i for i in range(len(names))]
    pg = connect()
    pc = pg.cursor()
    pc.execute("DROP TABLE IF EXISTS src.%s" % qi(name))
    pc.execute("CREATE TABLE src.%s (%s)" % (qi(name), ", ".join("%s text" % c for c in cols)))
    for s in range(0, len(kept), chunk):
        buf = io.StringIO("".join("\t".join(esc(v) for v in r) + "\n" for r in kept[s:s + chunk]))
        pc.copy_expert("COPY src.%s FROM STDIN" % qi(name), buf)
    pc.execute("ANALYZE src.%s" % qi(name))
    pg.commit()
    pg.close()
    print("%s: %d rows loaded into src.%s (%.1fs)" % (name, len(kept), name, time.time() - t0), flush=True)

def designs(name):
    """the record of experiments.py for the designs of meaningful.py: the iCONF and classical 3NF designs and the
    original relation with the non-key FDs of a minimal cover of every schema (for the exclusion constraints)"""
    mset = SETS[name][0]
    names, F = meaningful.fdset(mset)
    n = len(names)
    Da = atomic_cover(F, cap=MAX_MINIMAL)
    m = None
    for line in open(os.path.join(ROOT, "results", "meaningful_%s.jsonl" % mset), encoding="utf-8"):
        if line.strip():
            m = json.loads(line)
    idx = {a: i for i, a in enumerate(names)}
    R = (1 << n) - 1
    def des(key):
        d = [(mask([idx[a] for a in S]), [mask([idx[a] for a in K]) for K in keys]) for S, keys in m["designs"][key]["design"]]
        assert loss_of(Da, key_dependencies(n, d)) == m["designs"][key]["loss"], (name, key)
        return d
    rec = {"name": e1_name(name), "n": n, "fds": len(F), "minimal_fds": len(Da), "dropped_columns": [],
           "keys": len(m["keys"]), "nu": m["nu"], "lambda": m["lambda"]}
    rec["designs"] = {"orig": design_json(n, Da, [(R, minimal_keys(Da, R))], triggers=True),
                      "3nf": design_json(n, Da, des("iconf"), triggers=True),
                      "3nfc": design_json(n, Da, des("3nf-classical"), triggers=True)}
    for mode, key in (("bcnf", "bcnf-classical"), ("gbcnf", "bcnf-greedy"), ("repair", "repair"), ("drop", "drop")):
        rec["designs"][mode] = design_json(n, Da, des(key))
    for mode, key in (("3nf", "iconf"), ("3nfc", "3nf-classical"), ("bcnf", "bcnf-classical"), ("gbcnf", "bcnf-greedy"),
                      ("repair", "repair"), ("drop", "drop")):
        rec[mode + "_loss"] = m["designs"][key]["loss"]
    rec["bcnf_sound"] = m["designs"]["bcnf-classical"]["sound"]
    out = os.path.join(ROOT, "results", "e1_%s.jsonl" % safe(e1_name(name)))
    with open(out, "w", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print("%s: designs of %s written to %s" % (name, mset, os.path.relpath(out, ROOT)), flush=True)

def main():
    args = sys.argv[1:]
    action, names = args[0], args[1:] or list(SETS)
    for name in names:
        {"--clean": clean, "--load": load, "--designs": designs}[action](name)

if __name__ == "__main__":
    main()
