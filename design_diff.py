"""design_diff.py: tells for every FD set whether the Repair and Drop designs of the latest E1 record differ from
those of the earlier records, so that the operational experiments (E3, E4) are re-run only where the design changed.

    python3 design_diff.py [set ...]        # default: every results/e1_*.jsonl with at least two records

For every set it prints one line per earlier record with the losses of its designs and, for Repair and Drop, whether
the design (the schemata with their declared keys) equals the latest one."""
import glob, json, os, sys

def canon(design):
    if design is None:
        return None
    return tuple(sorted((tuple(sorted(s["attrs"])), tuple(sorted(tuple(sorted(k)) for k in s["keys"]))) for s in design))

def main(argv):
    files = sorted(glob.glob("results/e1_*.jsonl")) if not argv else ["results/e1_%s.jsonl" % s for s in argv]
    for f in files:
        recs = [json.loads(l) for l in open(f) if l.strip()]
        if len(recs) < 2:
            continue
        last = recs[-1]
        name = last.get("name", os.path.basename(f))
        ld = last.get("designs") or {}
        print("%-18s latest: repair %s drop %s (%d records)" % (name, last.get("repair_loss"), last.get("drop_loss"), len(recs)))
        for i, r in enumerate(recs[:-1]):
            d = r.get("designs") or {}
            flags = []
            for mode in ("repair", "drop"):
                if mode in ld or mode in d:
                    flags.append("%s %s" % (mode, "same" if canon(ld.get(mode)) == canon(d.get(mode)) else "DIFFERENT"))
            print("   record %d: repair %s drop %s -> %s" % (i, r.get("repair_loss"), r.get("drop_loss"), ", ".join(flags)))

if __name__ == "__main__":
    main(sys.argv[1:])
