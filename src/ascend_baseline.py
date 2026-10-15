r"""ascend_baseline.py: Ascend (Alg. 2) from the obstruction design alone, without the local repairs of Repair, on the
FD sets with positive loss (runs on the server, one process per set).

The atomic cover is that of E1 (experiments.sigma_a). The ascent starts from the uncritical minimal FDs of Sigma, as
the ascent from the obstruction design inside Repair does, and runs as ascend.ascend does: the deterministic climb,
then climbs in random candidate order until the budget (ASCEND_TIME of E1 by default) or 60 restarts. The record
holds the loss of the start, the anytime curve (seconds, loss of the lightest state so far), the final
loss, the time to reach it, and the check of the final design (sound, locally enforced, loss of its keys).

With --sideways=K the climbs also accept up to K consecutive exchanges that leave the loss unchanged
(ascend.Ascent._climb); with --kicks=K every climb continues as an iterated local search until K consecutive
random exchanges bring no improvement (ascend.Ascent.run), and --accept=better returns to the best state after
a kick that ends heavier; --start=repair (drop) starts from the uncritical minimal FDs of the design of Repair (Drop)
in the E1 record instead of the obstruction design; --seed=S seeds the random orders; --tag=T names the variant in
the file name; --secondary=1 prefers, among states of equal loss, those with fewer classes (Ascent.run).

usage: python3 ascend_baseline.py [--budget=1800] [--sideways=K] [--kicks=K] [--accept=walk|better]
       [--start=obstruction|repair|drop] [--seed=S] [--secondary=0|1] [--tag=T] <set> ...   results/ascend_baseline[_T]_<set>.json
"""
import sys, os, json, time, random
import experiments as e
from fdlib import load_any, loss_of, key_dependencies, check_bcnf_design, atomic_cover, mask
from ascend import Ascent, plain_start

SETS = ["abalone", "breast(null)", "bridges(null)", "echo(null)", "ncvoter(null)", "china_weather(null)",
        "tpch-lineitem", "uniprot(null)", "hepatitis(null)", "doc-food+c1", "doc-uk", "doc-hospital", "doc-tpcds"]

def e1_start(n, name, label):
    """the uncritical minimal FDs of the FD set enforced by the design `label` of the E1 record of the set"""
    rec = [json.loads(l) for l in open(os.path.join(e.ROOT, "results", "e1_%s.jsonl" % e.safe(name)), encoding="utf-8") if l.strip()][-1]
    design = [(mask(s["attrs"]), [mask(K) for K in s["keys"]]) for s in rec["designs"][label]]
    return plain_start(atomic_cover(key_dependencies(n, design)))

def run(name, budget, restarts=60, seed=0, max_schema=14, sideways=0, kicks=0, tag="", accept="walk", source="obstruction",
        secondary=False):
    n, F, _ = load_any(e.fd_path(name))
    Da, _ = e.sigma_a(n, F)
    R = (1 << n) - 1
    t0 = time.time()
    deadline = t0 + budget
    start = plain_start(Da) if source == "obstruction" else e1_start(n, name, source)
    base = Ascent(n, Da, None, R, start, max_schema, 0)
    if not base.plain():
        raise SystemExit("%s: the start is not a plain state" % name)
    out = {"set": name, "minimal_fds": len(Da), "budget": budget, "sideways": sideways, "kicks": kicks, "accept": accept,
           "start": source, "seed": seed, "secondary": secondary, "start_loss": base.loss(),
           "time_start": round(time.time() - t0, 1)}
    curve = [(round(time.time() - t0, 1), base.loss())]
    rng = random.Random(seed)
    best, runs = None, 0
    for i in range(1 + restarts):
        if i > 0 and time.time() > deadline:
            break
        asc = base if i == 0 else Ascent(n, Da, None, R, start, max_schema, 0)
        asc.run(deadline, None if i == 0 else rng, kicks, sideways, accept, secondary)
        runs += 1
        if i == 0:
            out["first_climb_loss"] = asc.loss()
            out["first_climb_seconds"] = round(time.time() - t0, 1)
        if best is None or (asc.loss(), asc.best_classes) < (best.loss(), best.best_classes):
            best = asc
            curve.append((round(time.time() - t0, 1), asc.loss(), asc.best_classes))
    out.update({"loss": best.loss(), "seconds_to_best": curve[-1][0], "seconds": round(time.time() - t0, 1),
                "runs": runs, "curve": curve})
    design = best.design()
    sound, local, _ = check_bcnf_design(n, design, Da)
    out.update({"schemata": len(design), "classes": best.classes(), "sound": sound, "local": local,
                "loss_check": loss_of(Da, key_dependencies(n, design))})
    with open(os.path.join(e.ROOT, "results", "ascend_baseline%s_%s.json" % ("_" + tag if tag else "", e.safe(name))), "w", encoding="utf-8") as f:
        f.write(json.dumps(out) + "\n")
    print("%-20s start %5d  first climb %5d (%.0fs)  best %5d after %.0fs  runs %d  schemata %d classes %d  sound %s local %s check %d"
          % (name, out["start_loss"], out["first_climb_loss"], out["first_climb_seconds"], out["loss"],
             out["seconds_to_best"], runs, out["schemata"], out["classes"], sound, local, out["loss_check"]), flush=True)

if __name__ == "__main__":
    budget, sideways, kicks, tag, accept, source, seed, secondary = e.ASCEND_TIME, 0, 0, "", "walk", "obstruction", 0, False
    names = []
    for a in sys.argv[1:]:
        if a.startswith("--budget="):
            budget = float(a[9:])
        elif a.startswith("--sideways="):
            sideways = int(a[11:])
        elif a.startswith("--kicks="):
            kicks = int(a[8:])
        elif a.startswith("--tag="):
            tag = a[6:]
        elif a.startswith("--accept="):
            accept = a[9:]
        elif a.startswith("--start="):
            source = a[8:]
        elif a.startswith("--seed="):
            seed = int(a[7:])
        elif a.startswith("--secondary="):
            secondary = a[12:] == "1"
        else:
            names.append(a)
    for name in names or SETS:
        run(name, budget, seed=seed, sideways=sideways, kicks=kicks, tag=tag, accept=accept, source=source, secondary=secondary)
