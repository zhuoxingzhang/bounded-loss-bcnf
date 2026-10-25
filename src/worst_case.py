r"""worst_case.py: the integrity risk of the designs of E4 over the choices that their algorithms leave open (E4).

3NF synthesis removes the redundant minimal FDs in the order in which they are listed (iCONF reorders them by its
ranks, so the order only breaks ties) and adds the minimal key of R that it finds by dropping attributes in index
order; the classical BCNF decomposition splits on the first violating FD; the greedy BCNF decomposition breaks ties
in favour of the first split; Repair starts from the decomposition of iCONF. Every order is as valid as the one of
E1, so run r > 0 relabels the attributes by a random permutation and lists Sigma_a in a random order
(random.Random(r)), runs the algorithm and maps the schemata back; run 0 keeps the order of E1 and reproduces its
design (the record says whether it does). For Repair, which keeps the budgets of E1, run 0 is its design in E1. The
3NF syntheses and the BCNF decompositions declare all minimal keys of their schemata, as in E1. Every distinct design
is evaluated on the updates of e4.py (the same seeds, so run 0 reproduces the risk of E4).

The record of a set holds, per mode, the number of runs, the runs that failed (Repair out of memory) and the distinct
designs with the runs that produce them, their number of schemata, loss and risk per seed; a later call with other
modes adds them to the record.

usage: python3 worst_case.py [--runs 100] [--runs-for set=8,...] [--workers 10] [--cap-gb 8]
                             [--modes 3nf,3nfc,bcnf,gbcnf,repair] [set ...]       results/worst_<set>.jsonl
       python3 worst_case.py --table
"""
import sys, os, json, time, random
import numpy as np
from multiprocessing import Pool

from fdlib import *
import experiments
from experiments import LOCAL_TIME, DROP_TIME, MAX_W, ASCEND_TIME, max_extra_for, sigma_a
from iconf import iconf_decomposition, decomp4
from repair import repair
from e3 import SETS, e1_record
from e4 import load_table, draw_updates, tested_fds, violations, key_dependencies_of

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODES = ["3nf", "3nfc", "bcnf", "gbcnf"]
SEEDS = [1, 2, 3, 4, 5]
UPDATES = 10000
CHUNK = 4000   # key dependencies per call of violations()

def relabel(X, pi):
    Y = 0
    for a in bits(X):
        Y |= 1 << pi[a]
    return Y

# the worker state: set by init() in every process
G = {}

def init(sets, cap):
    """sets: name -> (n, F, Sigma_a); cap: the address space of a worker in bytes (a run of Repair that needs more
    fails with MemoryError instead of being killed by the server)"""
    if cap:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (cap, cap))
    G.update(sets)

def ordered(name, r):
    """the permutation of the attributes and the relabelled, reordered Sigma_a of run r"""
    n, F, Da = G[name]
    if r == 0:
        return list(range(n)), Da
    rng = random.Random(r)
    pi = list(range(n))
    rng.shuffle(pi)
    fds = [(relabel(X, pi), pi[A]) for (X, A) in Da.fds]
    rng.shuffle(fds)
    return pi, FDSet(n, fds)

def design_of(task):
    """the design (a sorted tuple of (schema, keys)) of one mode in run r, in the original attributes, or None when
    Repair runs out of memory"""
    name, mode, r = task
    n, F, Da = G[name]
    pi, Dp = ordered(name, r)
    inv = [0] * n
    for a in range(n):
        inv[pi[a]] = a
    t0 = time.time()
    if mode == "repair":
        try:
            rr = repair(n, F, Da=Dp, local_time_limit=LOCAL_TIME, time_limit=DROP_TIME, max_w=MAX_W, max_extra=max_extra_for(n),
                        ascend_time=ASCEND_TIME, dec0=iconf_decomposition(n, Dp))
        except MemoryError:
            return name, mode, r, None, time.time() - t0
        des = [(relabel(S, inv), [relabel(K, inv) for K in keys]) for S, keys in rr.design]
    else:
        if mode == "3nf":
            dec = iconf_decomposition(n, Dp)
        elif mode == "3nfc":
            dec = decomp4(n, Dp)
        elif mode == "bcnf":
            dec = bcnf_decomposition(Dp)
        else:
            dec = greedy_bcnf_decomposition(Dp, time_limit=1800)[0]
        des = keyed(Da, [relabel(S, inv) for S in dec])
    return name, mode, r, tuple(sorted((S, tuple(sorted(keys))) for S, keys in des)), time.time() - t0

def as_json(n, des):
    return [dict(attrs=list(bits(S)), keys=[list(bits(K)) for K in keys]) for S, keys in des]

def canon(design_json):
    return sorted((tuple(s["attrs"]), tuple(sorted(tuple(k) for k in s["keys"]))) for s in design_json)

def generate(names, runs, workers, modes, cap):
    """the distinct designs per set and mode with their runs, from one pool over all sets (the runs of the sets
    where E1 took longest first); run 0 of Repair is its design in E1"""
    sets, recs, found, took, failed, tasks = {}, {}, {}, {}, {}, []
    for name in names:
        rec = recs[name] = e1_record(name)
        n, F, _ = load_any(experiments.fd_path(SETS[name]))
        Da, _ = sigma_a(n, F)
        assert len(Da) == rec["minimal_fds"], name
        sets[name] = (n, F, Da)
        ms = [m for m in modes if m in rec["designs"]]
        found[name], took[name], failed[name] = {m: {} for m in ms}, {m: 0.0 for m in ms}, {m: [] for m in ms}
        for m in ms:
            r0 = 0
            if m == "repair":
                e1 = tuple(sorted((mask(s["attrs"]), tuple(sorted(mask(K) for K in s["keys"]))) for s in rec["designs"]["repair"]))
                found[name][m][e1] = [0]
                r0 = 1
            tasks += [(name, m, r) for r in range(r0, runs.get(name, runs[None]))]
    tasks.sort(key=lambda t: -(recs[t[0]].get("time_repair") or 0) if t[1] == "repair" else 0)
    t0 = time.time()
    with Pool(workers, initializer=init, initargs=(sets, cap)) as pool:
        for k, (name, m, r, des, t) in enumerate(pool.imap_unordered(design_of, tasks)):
            if des is None:
                failed[name][m].append(r)
            else:
                found[name][m].setdefault(des, []).append(r)
            took[name][m] += t
            if (k + 1) % 50 == 0 or m == "repair":
                print("   %d/%d designs: %s %s run %d (%.0fs, %.0fs in all)" % (k + 1, len(tasks), name, m, r, t, time.time() - t0), flush=True)
    for name in names:
        print("%s: %s distinct designs" % (name, ", ".join("%s %d" % (m, len(found[name][m])) for m in found[name])), flush=True)
    return sets, recs, found, took, failed

def run(name, runs, sets, rec, found, took, failed):
    n, F, Da = sets[name]
    modes = list(found)
    out = {"set": name, "updates": UPDATES, "seeds": SEEDS, "modes": {}}
    for m in modes:
        e1 = canon(rec["designs"][m])
        out["modes"][m] = {"runs": runs.get(name, runs[None]), "failed": sorted(failed[m]), "time": round(took[m], 1), "designs": [
            {"runs": sorted(rs), "schemata": len(des), "loss": loss_of(Da, key_dependencies(n, list(des))), "risk": [],
             "e1": canon(as_json(n, des)) == e1, "design": as_json(n, des)} for des, rs in found[m].items()]}
        out["modes"][m]["designs"].sort(key=lambda d: d["runs"][0])
    # the risk of every distinct design on the updates of e4.py
    codes = load_table(name)
    sigma, cover = tested_fds(n, F)
    out["cover"] = cover
    deps = sorted({fd for m in modes for d in out["modes"][m]["designs"] for fd in key_dependencies_of(d["design"])})
    col = {fd: j for j, fd in enumerate(deps)}
    out["harmful"] = []
    for seed in SEEDS:
        t1 = time.time()
        upd_row, upd_attr, upd_val, mult = draw_updates(codes, n, UPDATES, seed)
        harmful = violations(codes, mult, sigma, upd_row, upd_attr, upd_val).any(axis=1)
        out["harmful"].append(int(harmful.sum()))
        packed = np.zeros((len(deps), (UPDATES + 7) // 8), dtype=np.uint8)
        for c in range(0, len(deps), CHUNK):
            V = violations(codes, mult, deps[c:c + CHUNK], upd_row, upd_attr, upd_val)
            packed[c:c + V.shape[1]] = np.packbits(V.T, axis=1)
        for m in modes:
            for d in out["modes"][m]["designs"]:
                idx = [col[fd] for fd in key_dependencies_of(d["design"])]
                caught = np.unpackbits(np.bitwise_or.reduce(packed[idx], axis=0))[:UPDATES].astype(bool) if idx else np.zeros(UPDATES, bool)
                missed = harmful & ~caught
                d["risk"].append(float(missed.sum() / harmful.sum()) if harmful.sum() else 0.0)
        print("   %s seed %d: %d harmful, %d key dependencies (%.0fs)" % (name, seed, harmful.sum(), len(deps), time.time() - t1), flush=True)
    path = os.path.join(ROOT, "results", "worst_%s.jsonl" % name)
    if os.path.isfile(path):   # keep the modes of an earlier run on the same updates
        old = json.loads(open(path, encoding="utf-8").readline())
        if (old["updates"], old["seeds"], old["harmful"]) == (UPDATES, SEEDS, out["harmful"]):
            for v in old["modes"].values():
                v.setdefault("runs", old.get("runs"))
            out["modes"] = {**old["modes"], **out["modes"]}
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(out) + "\n")
    for m in modes:
        ds = out["modes"][m]["designs"]
        risks = [np.mean(d["risk"]) for d in ds for _ in d["runs"]]
        print("   %-6s run 0 %s | risk %.2f to %.2f%% over %d runs, %d designs, loss %d to %d" % (
            m, "= E1" if ds[0]["e1"] else "differs from E1", 100 * min(risks), 100 * max(risks), len(risks), len(ds),
            min(d["loss"] for d in ds), max(d["loss"] for d in ds)), flush=True)

def table():
    for name in SETS:
        f = os.path.join(ROOT, "results", "worst_%s.jsonl" % name)
        if not os.path.isfile(f):
            continue
        r = json.loads(open(f, encoding="utf-8").readline())
        cells = []
        for m in MODES:
            if m not in r["modes"]:
                continue
            ds = r["modes"][m]["designs"]
            risks = sorted(100 * np.mean(d["risk"]) for d in ds for _ in d["runs"])
            e1 = 100 * np.mean(ds[0]["risk"])
            cells.append("%s %.1f [%.1f..%.1f] %dd%s" % (m, e1, risks[0], risks[-1], len(ds), "" if ds[0]["e1"] else "!"))
        print("%-10s %s" % (name, "  ".join(cells)))

def main():
    args = sys.argv[1:]
    runs, workers, cap, modes, names = {None: 100}, 10, None, MODES, []
    i = 0
    while i < len(args):
        if args[i] == "--runs":
            runs[None] = int(args[i + 1]); i += 2
        elif args[i] == "--runs-for":
            runs.update((k, int(v)) for k, v in (x.split("=") for x in args[i + 1].split(","))); i += 2
        elif args[i] == "--workers":
            workers = int(args[i + 1]); i += 2
        elif args[i] == "--cap-gb":
            cap = int(float(args[i + 1]) * 2**30); i += 2
        elif args[i] == "--modes":
            modes = args[i + 1].split(","); i += 2
        elif args[i] == "--table":
            table(); return
        else:
            names.append(args[i]); i += 1
    names = names or list(SETS)
    sets, recs, found, took, failed = generate(names, runs, workers, modes, cap)
    for name in names:
        run(name, runs, sets, recs[name], found[name], took[name], failed[name])

if __name__ == "__main__":
    main()
