"""Print the PostgreSQL E3 measurements (e3pg.py) per data set and design: exclusion constraints, UNIQUE constraints,
schemata, mean and standard deviation of the seconds per size, growth from 10,000 to 30,000 records, and the ratio to
the keys-only design at 10,000 records.  Usage: python3 e3_report.py"""
from paper_tables import load_e3, e3_summary, e3_mean, E3_ORDER

for name, recs in load_e3().items():
    print("==", name)
    keys10 = e3_mean(recs, "keys", 10000)[0]
    for mode, _ in E3_ORDER:
        d, times, cancelled, skipped, measured = e3_summary(recs, mode)
        if d is None:
            sk = [r.get("skipped") for r in recs if r.get("mode") == mode and r.get("skipped")]
            print("  %-7s %s" % (mode, sk[-1] if sk else "(not run)"))
            continue
        cells = []
        for size in (10000, 20000, 30000):
            m, sd, n, cut = e3_mean(recs, mode, size)
            cells.append("     --        " if m is None else "%8.2f+-%5.2f%s" % (m, sd, "" if n == 5 else "(%d)" % n))
        t10, t30 = e3_mean(recs, mode, 10000)[0], e3_mean(recs, mode, 30000)[0]
        growth = "" if (t10 is None or t30 is None) else "  x%.2f" % (t30 / t10)
        ratio = "" if (t10 is None or not keys10) else "  %.1fx keys" % (t10 / keys10)
        note = "" if measured == mode else "  = " + measured
        extra = "".join("  CANCELLED at %d after %.0f s" % (s, t) for s, t in sorted(cancelled.items()))
        extra += "".join("  SKIPPED %d" % s for s in sorted(skipped))
        print("  %-7s sch %5d uniq %4d excl %5d | %s%s%s%s%s" % (
            mode, d["schemata"], d["unique"] + d.get("unique_md5", 0), d["exclusion"], " ".join(cells), growth, ratio, note, extra))
