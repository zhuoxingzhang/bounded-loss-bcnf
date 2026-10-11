r"""gbcnf.py: the greedy BCNF decomposition (fdlib.greedy_bcnf_decomposition) on the FD sets of E1.

For every schema it splits, the greedy decomposition chooses the violating left-hand side whose split, completed by
the classical algorithm, leaves the fewest minimal FDs unenforced by the minimal keys of the resulting schemata.
The classical choice is examined first and wins ties, so the greedy never loses more than the classical BCNF
decomposition of E1. The atomic cover is computed as in experiments.py.

usage: python3 gbcnf.py [--time-limit 1800] [name ...]      one record per set in results/gbcnf_<name>.jsonl
       python3 gbcnf.py --table                             the records next to the classical decomposition
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdlib import *
import experiments
from experiments import SETS, safe, design_json, ASSUME_ATOMIC_ABOVE, MAX_MINIMAL

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)   # the repository root, which holds data/, results/ and iconf/

def atomic(F, n):
    if len(F) > ASSUME_ATOMIC_ABOVE and all(not any(F.implies(X & ~(1 << a), A) for a in bits(X)) for (X, A) in F.fds):
        return FDSet(n, sorted(set(F.fds))), True
    return atomic_cover(F, cap=MAX_MINIMAL), False

def evaluate(n, Da, dec):
    des = keyed(Da, dec)
    E = key_dependencies(n, des)
    try:
        sound = chase_lossless(n, dec, E) if len(dec) <= 40 else None
    except Exception:
        sound = None
    return des, loss_of(Da, E), sound

def run(name, time_limit):
    path = dict(SETS)[name]
    rec = {"name": name}
    t0 = time.time()
    n, F, _ = load_any(path)
    Da, assumed = atomic(F, n)
    rec.update(n=n, minimal_fds=len(Da), atomic_assumed=assumed, time_cover=round(time.time() - t0, 1))
    t1 = time.time()
    cdec = bcnf_decomposition(Da)
    _, rec["bcnf_loss"], rec["bcnf_sound"] = evaluate(n, Da, cdec)
    rec["bcnf_schemata"] = len(cdec)
    rec["time_bcnf"] = round(time.time() - t1, 2)
    gdec, st = greedy_bcnf_decomposition(Da, time_limit=time_limit)
    des, rec["gbcnf_loss"], rec["gbcnf_sound"] = evaluate(n, Da, gdec)
    rec["gbcnf_schemata"] = len(gdec)
    rec["gbcnf_bcnf"] = all(is_bcnf(Da, S) for S in gdec)
    rec["gbcnf_stats"] = st
    rec["time_gbcnf"] = round(st["time"], 2)
    rec["design"] = design_json(n, Da, des)
    with open(os.path.join(ROOT, "results", "gbcnf_%s.jsonl" % safe(name)), "w", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print("%-22s |Da| %6d  classical %6d (%d schemata%s)  greedy %6d (%d schemata%s)  %d rollouts, %d deviations%s, %.1fs"
          % (name, len(Da), rec["bcnf_loss"], len(cdec), "" if rec["bcnf_sound"] is not False else ", unsound",
             rec["gbcnf_loss"], len(gdec), "" if rec["gbcnf_sound"] is not False else ", unsound",
             st["rollouts"], st["deviations"], ", TIMED OUT" if st["timed_out"] else "", st["time"]), flush=True)
    return rec

def table():
    for name, _ in SETS:
        f = os.path.join(ROOT, "results", "gbcnf_%s.jsonl" % safe(name))
        if not os.path.exists(f):
            continue
        r = json.loads(open(f, encoding="utf-8").readline())
        print("%-22s %6d  classical %6d%s  greedy %6d%s  time %.1fs%s" % (
            name, r["minimal_fds"], r["bcnf_loss"], "" if r["bcnf_sound"] is not False else "+",
            r["gbcnf_loss"], "" if r["gbcnf_sound"] is not False else "+", r["time_gbcnf"],
            " (timed out)" if r["gbcnf_stats"]["timed_out"] else ""))

if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--table"]:
        table()
        sys.exit(0)
    limit = 1800
    if args[:1] == ["--time-limit"]:
        limit = float(args[1])
        args = args[2:]
    names = args or [name for name, _ in SETS if name not in ("diabetic(null)", "fd-red")]
    for name in names:
        run(name, limit)
