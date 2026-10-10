"""design_diff.py: tells for every FD set whether the Repair and Drop designs of the latest E1 record differ from
earlier ones, so that the operational experiments (E3, E4) are re-run only where the design changed.

    python3 design_diff.py [--against DIR ...] [set ...]

Without --against, the earlier records are the earlier lines of results/e1_<set>.jsonl. With --against DIR, the
earlier record is the last line of DIR/e1_<set>.jsonl (a backup of a previous run), one line per DIR. For every
comparison it prints the losses of the designs and, for Repair and Drop, whether the design (the schemata with
their declared keys) equals the latest one, together with the modification times that tell which run an E3 or E4
record was made from."""
import glob, json, os, sys, time

def canon(design):
    if design is None:
        return None
    return tuple(sorted((tuple(sorted(s["attrs"])), tuple(sorted(tuple(sorted(k)) for k in s["keys"]))) for s in design))

def load(path):
    return [json.loads(l) for l in open(path) if l.strip()]

def mtime(path):
    return time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(path)))

def flags(last, r):
    out = []
    ld, d = last.get("designs") or {}, r.get("designs") or {}
    for mode in ("repair", "drop"):
        if mode in ld or mode in d:
            out.append("%s %s" % (mode, "same" if canon(ld.get(mode)) == canon(d.get(mode)) else "DIFFERENT"))
    return "repair %s drop %s -> %s" % (r.get("repair_loss"), r.get("drop_loss"), ", ".join(flags_ for flags_ in out))

def main(argv):
    against = []
    while "--against" in argv:
        i = argv.index("--against")
        against.append(argv[i + 1])
        del argv[i:i + 2]
    files = sorted(glob.glob("results/e1_*.jsonl")) if not argv else ["results/e1_%s.jsonl" % s for s in argv]
    for f in files:
        recs = load(f)
        if not recs:
            continue
        last = recs[-1]
        name = last.get("name", os.path.basename(f))
        print("%-18s latest (%s): repair %s drop %s" % (name, mtime(f), last.get("repair_loss"), last.get("drop_loss")))
        for i, r in enumerate(recs[:-1]):
            print("   record %d: %s" % (i, flags(last, r)))
        for d in against:
            g = os.path.join(d, os.path.basename(f))
            if os.path.exists(g):
                print("   %s (%s): %s" % (g, mtime(g), flags(last, load(g)[-1])))
        for e in ("e3", "e4"):
            g = "results/%s_%s.jsonl" % (e, os.path.basename(f)[3:-6].replace("_null_", "").replace("china_", "").replace("tpch-", "tpch_"))
            if os.path.exists(g):
                print("   %s: %s" % (g, mtime(g)))

if __name__ == "__main__":
    main(sys.argv[1:])
