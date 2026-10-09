"""Print the E3 measurements per data set and design: trigger checks, mean seconds per size, growth from 10,000 to
30,000 records, and the ratio to the keys-only design.  Usage: python3 e3_report.py"""
import json, os, statistics
import e3
from paper_tables import load_e3, e3_summary, E3_ORDER

recs_by_set = load_e3()
for name, recs in recs_by_set.items():
    print("==", name)
    base = None
    rows = []
    for mode, label in E3_ORDER:
        m = mode
        d, times, skipped = e3_summary(recs, m)
        note = ""
        if d is None and skipped and skipped.startswith("same design as "):
            m = skipped[len("same design as "):]
            d, times, _ = e3_summary(recs, m)
            note = "= " + m
        if d is None:
            print("  %-8s %s" % (mode, skipped or "(not run)"))
            continue
        to = [r for r in recs if r.get("mode") == m and "timeout_seconds" in r]
        tr = [r for r in recs if r.get("mode") == m and r.get("truncated") and "timeout_seconds" not in r]
        rows.append((mode, d, times, note, to, tr))
    keys = next((t for mo, d, t, n, to, tr in rows if mo == "keys"), {})
    for mode, d, times, note, to, tr in rows:
        t10, t20, t30 = (times.get(s) for s in (10000, 20000, 30000))
        f = lambda x: "    --" if x is None else "%6.1f" % x
        growth = "" if (t10 is None or t30 is None) else "  x%.2f" % (t30 / t10)
        ratio = "" if (t10 is None or not keys.get(10000)) else "  %.1fx keys" % (t10 / keys[10000])
        extra = ""
        if to:
            extra += "  TIMEOUT size %d after %.0f s with %d rows" % (to[0]["size"], to[0]["timeout_seconds"], to[0].get("inserted_before_timeout", 0))
        if tr:
            extra += "  truncated: " + tr[-1]["truncated"]
        print("  %-8s sch %5d uniq %3d idx %3d trig %5d | %s %s %s%s%s %s%s" % (
            mode, d["schemata"], d["unique"], d["indexes"], d["fd_triggers"] + d["key_triggers"], f(t10), f(t20), f(t30), growth, ratio, note, extra))
