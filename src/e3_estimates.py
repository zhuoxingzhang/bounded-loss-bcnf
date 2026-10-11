"""estimates.py: PLACEHOLDER insertion times for the E3 modes that have not been measured yet (2026-10-11), written to
results/e3pg_estimates.jsonl in the record format of e3pg.py with "estimated": true and a "basis" string.
paper_tables.load_e3 merges a mode of this file only while the real file has no completed measurement of that mode,
so every estimate disappears as soon as the real run lands. Delete the file when E3 is final. Run from tools/ (python e3_estimates.py)."""
import json, os, statistics, sys
sys.path.insert(0, os.getcwd())
import e3
from paper_tables import e3_mean, e3_summary
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository root, which holds data/ and results/

OUT = os.path.join(ROOT, "results", "e3pg_estimates.jsonl")
SIZE = 10000

def real(name):
    f = os.path.join(ROOT, "results", "e3pg_%s.jsonl" % name)
    return [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()] if os.path.isfile(f) else []

def measured(recs, mode):
    return e3_mean(recs, mode, SIZE)[0]

def design(recs, mode):
    return e3_summary(recs, mode)[0]

out, notes = [], []

def est(name, mode, seconds, basis, schemata, unique, exclusion, loss=None):
    out.append(dict(set=name, mode=mode, design=True, loss=loss, rows=None, copy=True, schemata=schemata, unique=unique,
                    unique_md5=0, exclusion=exclusion, trigger_fds=0, indexes=0, build_seconds=None, estimated=True, basis=basis))
    for rep in range(5):
        out.append(dict(set=name, mode=mode, size=SIZE, rep=rep, seconds=round(seconds, 3), inserted=None, attempted=None, estimated=True))
    notes.append("%-12s %-7s %8.1f s  %s" % (name, mode, seconds, basis))

def same(name, mode, as_mode):
    out.append(dict(set=name, mode=mode, skipped="same design as " + as_mode, same_as=as_mode, estimated=True))
    notes.append("%-12s %-7s = %s" % (name, mode, as_mode))

# per-schema insertion cost of a key design at 10,000 records, from the measured sets (basis of the schema-count rule)
RATE_SMALL = 0.145      # s per schema: median of breast 0.13, bridges 0.16, echo 0.16, ncvoter 0.135 (tables of at most 1,000 rows)
RATE_WEATHER = 0.30     # s per schema on 262,920-row tables: letter (18,668 rows) 0.26, adult (32,537 rows) 0.18, rounded up
EXCL_WEATHER = 1.8      # s per exclusion constraint per 10,000 records on 262,920-row tables: 0.7 to 1.4 on the other sets

for name in e3.SETS:
    recs = real(name)
    if not recs:
        continue
    rec = e3.e1_record(name)
    s3, s3c, sr = rec.get("3nf_schemata"), rec.get("3nfc_schemata"), rec.get("repair_schemata")
    d3, d3c = design(recs, "3nf-x"), design(recs, "3nfc-x")
    keys_t = measured(recs, "keys")
    # ---- the unmeasured modes of hepatitis and weather
    if name == "hepatitis":
        if measured(recs, "bcnf") is None:
            est(name, "bcnf", 2.5, "greedy BCNF (11 schemata, 24 UNIQUE) measured 2.3 s; BCNF has 16 schemata, 18 UNIQUE", 16, 18, 0, rec.get("bcnf_loss"))
        if measured(recs, "repair") is None:
            est(name, "repair", sr * RATE_SMALL, "%d schemata x %.3f s per schema (median rate of the key designs on breast, bridges, echo, ncvoter)" % (sr, RATE_SMALL),
                sr, None, 0, rec.get("repair_loss"))
    if name == "weather":
        if measured(recs, "orig-x") is None:
            est(name, "orig-x", 516 * EXCL_WEATHER + keys_t, "516 exclusion constraints x %.1f s + keys %.1f s" % (EXCL_WEATHER, keys_t), 1, 2, 516, 0)
        if measured(recs, "3nf-x") is None:
            est(name, "3nf-x", 222 * EXCL_WEATHER + 407 * RATE_WEATHER, "222 exclusion constraints x %.1f s + 407 schemata x %.2f s" % (EXCL_WEATHER, RATE_WEATHER), 407, 557, 222, rec.get("3nf_loss"))
        if measured(recs, "3nfc-x") is None:
            est(name, "3nfc-x", 226 * EXCL_WEATHER + 403 * RATE_WEATHER, "226 exclusion constraints x %.1f s + 403 schemata x %.2f s" % (EXCL_WEATHER, RATE_WEATHER), 403, 553, 226, rec.get("3nfc_loss"))
        if measured(recs, "repair") is None:
            est(name, "repair", 476 * RATE_WEATHER, "476 schemata x %.2f s per schema" % RATE_WEATHER, 476, 507, 0, rec.get("repair_loss"))
        if measured(recs, "drop") is None and design(recs, "drop") is None:
            same(name, "drop", "repair")      # the templates of repair and drop are identical (476 schemata, 507 UNIQUE)
    # ---- the keys-only 3NF syntheses of the Pareto figure
    for mode, mx, sch in (("3nf", "3nf-x", s3), ("3nfc", "3nfc-x", s3c)):
        if measured(recs, mode) is not None or design(recs, mode) is not None:
            continue
        dx = design(recs, mx)
        if dx is not None and dx.get("exclusion") == 0:
            same(name, mode, e3_summary(recs, mx)[4])     # no non-key FD enforced: the -x design is the keys-only design
        elif sch == 1:
            same(name, mode, "keys")
        else:
            # schema-count rule: the key design of Repair on the same set, scaled by the number of schemata
            rt = measured(recs, "repair")
            if rt is None:
                rt = next((r["seconds"] for r in out if r["set"] == name and r["mode"] == "repair" and "seconds" in r), None)
            rs = sr if design(recs, "repair") is None or e3_summary(recs, "repair")[4] == "repair" else None
            if rt is None or not rs:
                notes.append("%-12s %-7s NO ESTIMATE" % (name, mode))
                continue
            est(name, mode, max(keys_t, rt * sch / rs), "%d schemata x (Repair %.1f s / %d schemata)" % (sch, rt, rs), sch, None, 0,
                rec.get("3nf_loss" if mode == "3nf" else "3nfc_loss"))

with open(OUT, "w", encoding="utf-8") as f:
    for r in out:
        f.write(json.dumps(r) + "\n")
print("\n".join(notes))
print("written", OUT, len(out), "records")
