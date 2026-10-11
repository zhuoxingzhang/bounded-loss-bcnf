"""embedded_loss.py: how many of the minimal FDs that a Repair or Drop design leaves unenforced are embedded in one
of its schemata, so that a row-level trigger on that table could enforce them, and how many span several schemata,
so that a trigger would have to join tables.

    python embedded_loss.py [--tex] [set ...]     # E1 names; default: the data sets of e3.py with positive loss
                                                 # --tex also writes results/table_embedded.tex
"""
import json, os, sys
from fdlib import FDSet, atomic_cover, key_dependencies, unenforced, mask, load_any
import experiments
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository root, which holds data/ and results/

DEFAULT = ["abalone", "breast(null)", "bridges(null)", "echo(null)", "ncvoter(null)", "china_weather(null)", "hepatitis(null)"]

def design_masks(d):
    return [(mask(s["attrs"]), [mask(k) for k in s["keys"]]) for s in d]

def analyse(names):
    """[(name, {mode: (loss, embedded, across)})]"""
    paths = dict(experiments.SETS)
    out = []
    for name in names:
        f = os.path.join(ROOT, "results", "e1_%s.jsonl" % experiments.safe(name))
        r = json.loads(open(f, encoding="utf-8").read().splitlines()[-1])
        n, F, _ = load_any(paths[name])
        Da = F if r.get("atomic_assumed") else atomic_cover(F)
        row = {}
        for mode in ("repair", "drop"):
            d = (r.get("designs") or {}).get(mode)
            if not d:
                continue
            design = design_masks(d)
            delta = unenforced(Da, key_dependencies(n, design))
            emb = sum(1 for X, A in delta if any((X | (1 << A)) & ~S == 0 for S, _ in design))
            row[mode] = (len(delta), emb, len(delta) - emb)
        out.append((name, row))
    return out

def table(rows):
    from paper_tables import tex_name, num
    out = [r"\begin{tabular}{lrrrrrr}", r"\toprule",
           r"Data set & \multicolumn{3}{c}{\repair} & \multicolumn{3}{c}{\drop}\\",
           r"\cmidrule(lr){2-4}\cmidrule(lr){5-7}",
           r" & loss & inside & across & loss & inside & across\\", r"\midrule"]
    for name, row in rows:
        cells = []
        for mode in ("repair", "drop"):
            t = row.get(mode)
            cells += ["--", "--", "--"] if t is None else [num(x) for x in t]
        out.append("%s & %s\\\\" % (tex_name(name), " & ".join(cells)))
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)

def main(argv):
    tex = "--tex" in argv
    names = [a for a in argv if a != "--tex"] or DEFAULT
    rows = analyse(names)
    for name, row in rows:
        for mode, (loss, emb, across) in row.items():
            print("%-20s %-6s loss %5d  inside a schema %5d  across schemata %5d" % (name, mode, loss, emb, across))
    if tex:
        t = table(rows)
        open(os.path.join(ROOT, "results", "table_embedded.tex"), "w", encoding="utf-8", newline="\n").write(t + "\n")
        print(t)

if __name__ == "__main__":
    main(sys.argv[1:])
