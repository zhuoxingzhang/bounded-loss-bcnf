"""drop_constants.py: removes the constant attributes from the FD files, that is, the attributes A with the FD
{} -> A in the discovered set, as the paper assumes that no attribute is constant (Section 2).

    python src/drop_constants.py            # rewrites the files of experiments.DROPPED_COLUMNS, keeps the originals
    python src/drop_constants.py --check    # verifies that the files on disk are the discovered files minus the columns

A constant attribute A carries no information: {} -> A is its only minimal FD with right-hand side A, and A occurs
in no minimal left-hand side, since X - A -> X holds for every X that contains A. Removing A therefore removes
exactly the minimal FD {} -> A and renumbers the attributes above A. The discovered files are kept under
data/fds/discovered/ with the same relative path, and the record of every run lists the removed columns under
"dropped_columns". The data files of E3 and E4 keep all columns; experiments.source_columns() maps the attributes
of a set to its columns.
"""
import json, os, shutil, sys
import experiments
from fdlib import load_any, bits, mask
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FDS = os.path.join(ROOT, "data", "fds")
DISC = os.path.join(FDS, "discovered")

def renumber(a, dropped):
    """the new index of attribute a after removing the attributes in dropped (none of them equal to a)"""
    return a - sum(1 for d in dropped if d < a)

def rewrite_json(path, dropped):
    d = json.load(open(path, encoding="utf-8"))
    out = []
    for x in d["fds"]:
        assert not set(x["lhs"]) & set(dropped), (path, x)
        rhs = [r for r in x["rhs"] if r not in dropped]
        if set(x["rhs"]) & set(dropped):
            assert x["lhs"] == [], (path, x)      # a constant attribute is determined by the empty set only
        if rhs:
            out.append({"lhs": [renumber(a, dropped) for a in x["lhs"]], "rhs": [renumber(a, dropped) for a in rhs]})
    d["R"] = d["R"] - len(dropped)
    d["fds"] = out
    d["dropped_columns"] = sorted(dropped)
    s = json.dumps(d, indent=1).replace("\n   ", "\n\t\t").replace("\n  ", "\n\t")
    open(path, "w", encoding="utf-8", newline="\n").write(s + "\n")

def rewrite_txt(path, dropped):
    """Metanome text format with 1-based column ids"""
    out, section = [], None
    ids = [a + 1 for a in dropped]
    for line in open(path, encoding="utf-8"):
        raw = line.rstrip("\n")
        s = raw.strip()
        if s.startswith("#"):
            section = s[1:].strip().upper()
            out.append(raw)
            continue
        if section == "COLUMN" and s:
            name, idx = s.rsplit("\t", 1)
            if int(idx) in ids:
                continue
            out.append("%s\t%d" % (name, renumber(int(idx), ids)))
        elif section == "RESULTS" and s:
            lhs, rhs = s.split("->")
            L = [int(t) for t in lhs.split(",") if t]
            Rs = [int(t) for t in rhs.split(",") if t and int(t) not in ids]
            assert not set(L) & set(ids), (path, s)
            if Rs:
                out.append("%s->%s" % (",".join(str(renumber(a, ids)) for a in L), ",".join(str(renumber(a, ids)) for a in Rs)))
        else:
            out.append(raw)
    open(path, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")

def main(argv):
    paths = dict(experiments.SETS)
    for name, dropped in experiments.DROPPED_COLUMNS.items():
        path = paths[name]
        rel = os.path.relpath(path, FDS)
        keep = os.path.join(DISC, rel)
        if "--check" in argv:
            n0, F0, _ = load_any(keep)
            n1, F1, _ = load_any(path)
            want = set()
            for X, A in F0.fds:
                if A in dropped:
                    assert X == 0, (name, X, A)
                    continue
                assert not set(bits(X)) & set(dropped), (name, X, A)
                want.add((mask(renumber(a, dropped) for a in bits(X)), renumber(A, dropped)))
            assert n1 == n0 - len(dropped) and set(F1.fds) == want, name
            print("%-16s ok: %d -> %d attributes, %d -> %d minimal FDs" % (name, n0, n1, len(F0.fds), len(F1.fds)))
            continue
        if os.path.exists(keep):
            print("%-16s already rewritten (%s exists)" % (name, os.path.relpath(keep, ROOT)))
            continue
        os.makedirs(os.path.dirname(keep), exist_ok=True)
        shutil.copyfile(path, keep)
        (rewrite_txt if path.endswith(".txt") else rewrite_json)(path, dropped)
        n1, F1, _ = load_any(path)
        print("%-16s dropped columns %s: now %d attributes, %d minimal FDs" % (name, dropped, n1, len(F1.fds)))

if __name__ == "__main__":
    main(sys.argv[1:])
