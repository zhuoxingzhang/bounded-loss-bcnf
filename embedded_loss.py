"""embedded_loss.py: how many of the minimal FDs that a Repair or Drop design leaves unenforced are embedded in one
of its schemata, so that a row-level trigger on that table could enforce them (the variant "Repair with triggers"
of the operational experiments), and how many are embedded in no schema.

    python embedded_loss.py [set ...]     # E1 names, default: the data sets of e3.py with positive loss
"""
import json, os, sys
from fdlib import FDSet, atomic_cover, key_dependencies, unenforced, mask, load_any
import experiments

DEFAULT = ["abalone", "breast(null)", "bridges(null)", "echo(null)", "ncvoter(null)", "china_weather(null)", "hepatitis(null)"]

def design_masks(d):
    return [(mask(s["attrs"]), [mask(k) for k in s["keys"]]) for s in d]

def main(argv):
    names = argv or DEFAULT
    paths = dict(experiments.SETS)
    for name in names:
        f = os.path.join("results", "e1_%s.jsonl" % experiments.safe(name))
        r = json.loads(open(f, encoding="utf-8").read().splitlines()[-1])
        n, F, _ = load_any(paths[name])
        Da = F if r.get("atomic_assumed") else atomic_cover(F)
        for mode in ("repair", "drop"):
            d = (r.get("designs") or {}).get(mode)
            if not d:
                continue
            design = design_masks(d)
            E = key_dependencies(n, design)
            delta = unenforced(Da, E)
            emb = [(X, A) for X, A in delta if any((X | (1 << A)) & ~S == 0 for S, _ in design)]
            per_schema = sum(1 for S, _ in design if any((X | (1 << A)) & ~S == 0 for X, A in delta))
            print("%-20s %-6s loss %5d  embedded in a schema %5d  in no schema %5d  schemata with a trigger %d of %d" % (
                name, mode, len(delta), len(emb), len(delta) - len(emb), per_schema, len(design)))

if __name__ == "__main__":
    main(sys.argv[1:])
