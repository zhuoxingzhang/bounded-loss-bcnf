"""embedded_loss.py: how many of the minimal FDs that a design leaves unenforced are embedded in one of its schemata,
so that an exclusion constraint or a row-level trigger on that table could enforce them, and how many span several
schemata, so that a trigger would have to join tables. All eight key designs of the paper are analysed: the key-only
design (orig), the two 3NF syntheses (3nf by iConf, 3nfc classical), the classical and the greedy BCNF
decomposition (bcnf, gbcnf), Hybrid, Repair and Drop, from the records of experiments.py, gbcnf.py and hybrid.py.

    python embedded_loss.py [--tex] [set ...]     # E1 names; default: the data sets of e3.py with positive loss
                                                 # --tex also writes results/table_embedded.tex
"""
import json, os, sys
from fdlib import FDSet, atomic_cover, key_dependencies, unenforced, mask, load_any
import experiments
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository root, which holds data/ and results/

DEFAULT = ["abalone", "breast(null)", "bridges(null)", "echo(null)", "ncvoter(null)", "china_weather(null)", "hepatitis(null)",
           "doc-food+c1", "doc-uk", "doc-hospital", "doc-tpcds"]   # then the documented sets with data (documented.py)
MODES = [("orig", "key-only"), ("bcnf", "BCNF"), ("gbcnf", "greedy"), ("3nf", "iConf"), ("3nfc", "classical"),
         ("hybrid", "Hybrid"), ("repair", r"\repair"), ("drop", r"\drop")]
MODES, LABELS = [m for m, _ in MODES], dict(MODES)

def design_masks(d):
    return [(mask(s["attrs"]), [mask(k) for k in s["keys"]]) for s in d]

def analyse(names):
    """[(name, {mode: (loss, embedded, across)})]"""
    out = []
    for name in names:
        f = os.path.join(ROOT, "results", "e1_%s.jsonl" % experiments.safe(name))
        r = json.loads(open(f, encoding="utf-8").read().splitlines()[-1])
        n, F, _ = load_any(experiments.fd_path(name))
        Da = F if r.get("atomic_assumed") else atomic_cover(F)
        designs = dict(r.get("designs") or {})
        for fn, key, mode in (("gbcnf_%s.jsonl", "design", "gbcnf"), ("hybrid_%s.jsonl", "hybrid_design", "hybrid")):
            g = os.path.join(ROOT, "results", fn % experiments.safe(name))
            if os.path.exists(g):
                designs[mode] = json.loads(open(g, encoding="utf-8").read().splitlines()[-1]).get(key)
        row = {}
        for mode in MODES:
            d = designs.get(mode)
            if not d:
                continue
            design = design_masks(d)
            delta = unenforced(Da, key_dependencies(n, design))
            emb = sum(1 for X, A in delta if any((X | (1 << A)) & ~S == 0 for S, _ in design))
            row[mode] = (len(delta), emb, len(delta) - emb)
        out.append((name, row))
    return out

def load_independence():
    """{(set, mode): whether the design is independent} from results/independence.jsonl (independence.py)"""
    f = os.path.join(ROOT, "results", "independence.jsonl")
    out = {}
    if os.path.isfile(f):
        for l in open(f, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                out[(r["set"], "orig" if r["design"] == "keys" else r["design"])] = r["independent"]
    return out

def table(rows):
    """one column per design with the number of unenforced minimal FDs that span several schemata; the loss of
    every design is in the main table, and the difference lies inside one schema; a last row counts the sets on
    which the design is independent, out of those on which it ran"""
    from paper_tables import tex_name, num
    out = [r"\begin{tabular}{l" + "r" * len(MODES) + "}", r"\toprule",
           r"Data set & " + " & ".join(LABELS[m] for m in MODES) + r"\\", r"\midrule"]
    for name, row in rows:
        if name in experiments.DOCUMENTED and name == next(n for n, _ in rows if n in experiments.DOCUMENTED):
            out.append(r"\midrule")   # the documented sets follow the discovered ones
        cells = ["--" if row.get(m) is None else num(row[m][2]) for m in MODES]
        out.append("%s & %s\\\\" % (tex_name(name), " & ".join(cells)))
    ind = load_independence()
    if ind:
        cells = []
        for m in MODES:
            xs = [ind[(name, m)] for name, row in rows if m in row and (name, m) in ind]
            cells.append("%d/%d" % (sum(xs), len(xs)))
        out += [r"\midrule", "independent & %s\\\\" % " & ".join(cells)]
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)

def main(argv):
    tex = "--tex" in argv
    names = [a for a in argv if a != "--tex"] or DEFAULT
    rows = analyse(names)
    for name, row in rows:
        for mode in MODES:
            if mode in row:
                loss, emb, across = row[mode]
                print("%-20s %-7s loss %5d  inside a schema %5d  across schemata %5d" % (name, mode, loss, emb, across))
    if tex:
        t = table(rows)
        open(os.path.join(ROOT, "results", "table_embedded.tex"), "w", encoding="utf-8", newline="\n").write(t + "\n")
        print(t)

if __name__ == "__main__":
    main(sys.argv[1:])
