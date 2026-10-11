"""e3_refresh.py: drop the records of given modes from results/e3_<set>.jsonl before a mode is re-run.

usage: python3 e3_refresh.py <set> <mode>[,<mode>...]
The file is backed up to results/e3_<set>.<timestamp>.jsonl first. e3.py appends records, so a mode whose design
changed (for example after a change of Repair) must be removed before the driver runs it again.
"""
import json, os, shutil, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)   # the repository root, which holds data/, results/ and iconf/

def refresh(name, modes):
    f = os.path.join(ROOT, "results", "e3_%s.jsonl" % name)
    if not os.path.isfile(f):
        print("no records for", name)
        return
    bak = os.path.join(ROOT, "results", "e3_%s.%s.jsonl" % (name, time.strftime("%Y%m%d-%H%M%S")))
    shutil.copy(f, bak)
    kept, dropped = [], 0
    for line in open(f, encoding="utf-8"):
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("mode") in modes:
            dropped += 1
        else:
            kept.append(line)
    with open(f, "w", encoding="utf-8") as out:
        out.writelines(kept)
    print("%s: dropped %d records of modes %s, kept %d (backup %s)" % (name, dropped, ",".join(sorted(modes)), len(kept), os.path.basename(bak)))

if __name__ == "__main__":
    refresh(sys.argv[1], set(sys.argv[2].split(",")))
