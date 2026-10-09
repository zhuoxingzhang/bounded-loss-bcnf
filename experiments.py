r"""experiments.py: loss statistics of classical designs, Repair and Drop on the FD sets in data/fds (Metanome FDs
on complete and incomplete data, TPC-H): the prototype of experiment E1.

For every FD set: n, |Sigma| (atomic input FDs), |Sigma_a| (minimal FDs), the minimal keys, nu (non-key minimal
FDs = loss of the key-only design), whether Sigma^+ is enforceable (lambda = 0), the loss of 3NF synthesis
with all minimal keys declared (BCNF whenever possible), the loss and soundness of the classical BCNF
decomposition, the critical schemata of the 3NF decomposition, Repair (mode, loss, certified lower bound of
the local searches, time) and, when the schema is small enough, Drop on the whole schema.

usage: python experiments.py [--parallel K] [name-filter]   every FD set in its own process (K at a time,
       DATASET_TIMEOUT each; records in results/e1_<name>.jsonl), python experiments.py --one <name> for one set,
       python experiments.py --table for the table of the records.
"""
import sys, os, json, time, glob, traceback
from fdlib import *
from drop import drop
from repair import repair

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "fds")          # the FD sets shipped with the repository
COMPLETE, NULLEQ, TPCH = os.path.join(DATA, "complete"), os.path.join(DATA, "null-equality"), os.path.join(DATA, "tpch")
SETS = []
for f in sorted(glob.glob(os.path.join(COMPLETE, "*.json"))):
    name = os.path.basename(f)[:-5]
    if name == "lineitem-500k":
        continue
    SETS.append((name, f))
for f in sorted(glob.glob(os.path.join(NULLEQ, "*.json"))):
    SETS.append((os.path.basename(f)[:-5] + "(null)", f))
for f in sorted(glob.glob(os.path.join(TPCH, "*.txt"))):
    SETS.append(("tpch-" + os.path.basename(f)[:-8], f))
# small first
ORDER = ["tpch-region", "tpch-nation", "tpch-partsupp", "tpch-supplier", "tpch-customer", "tpch-orders", "tpch-part",
         "abalone", "breast(null)", "pdbx(null)", "bridges(null)", "echo(null)", "adult", "letter(non-dup)",
         "ncvoter(null)", "china_weather(null)", "tpch-lineitem", "lineitem", "uniprot(null)", "hepatitis(null)",
         "diabetic(null)", "fd-red"]
SETS.sort(key=lambda t: ORDER.index(t[0]) if t[0] in ORDER else 99)

MAX_MINIMAL = 300000      # cap on |Sigma_a|
ASSUME_ATOMIC_ABOVE = 2000  # above this many input FDs the discovered set is taken as Sigma_a (after checking that
                            # every left-hand side is minimal); on every smaller set the computed Sigma_a equals the input
DROP_MAX_MINIMAL = 1000   # run Drop on the whole schema only when |Sigma_a| is at most this
LOCAL_TIME = 120          # seconds per critical schema in Repair
DROP_TIME = 600           # seconds for the global Drop / fallback
ASCEND_TIME = 300         # seconds for the ascent (Algorithm "Ascend") in Repair and in the heuristic of Drop
MAX_W = 4                 # weakened FDs per candidate
DATASET_TIMEOUT = 14400   # seconds per FD set (each runs in its own process)

def max_extra_for(n):
    return None if n <= 12 else 3

def design_json(n, Da, design, triggers=False, max_cover=10000):
    """The schemata of a key design as attribute lists with their keys and, with triggers, the non-key FDs of
    a minimal cover of the projection that a trigger has to enforce (experiment E3)."""
    out = []
    for S, keys in design:
        d = {"attrs": list(bits(S)), "keys": [list(bits(K)) for K in keys]}
        if triggers:
            DaS = Da.restrict(S)
            if len(DaS) <= max_cover:
                C = minimal_cover(DaS)
                d["fds"] = [[list(bits(X)), A] for (X, A) in C.fds if DaS.closure(X) & S != S]
            else:
                d["fds"] = None
        out.append(d)
    return out

def run(name, path):
    rec = {"name": name}
    t0 = time.time()
    n, F, names = load_any(path)
    rec["n"] = n
    rec["fds"] = len(F)
    try:
        if len(F) > ASSUME_ATOMIC_ABOVE and all(not any(F.implies(X & ~(1 << a), A) for a in bits(X)) for (X, A) in F.fds):
            Da = FDSet(n, sorted(set(F.fds)))
            rec["atomic_assumed"] = True
        else:
            Da = atomic_cover(F, cap=MAX_MINIMAL)
    except CapExceeded as e:
        rec["error"] = "atomic cover: " + str(e)
        rec["time_cover"] = time.time() - t0
        return rec
    rec["time_cover"] = time.time() - t0
    rec["minimal_fds"] = len(Da)
    R = (1 << n) - 1
    keys_R = minimal_keys(Da, R)
    rec["keys"] = len(keys_R)
    rec["nu"] = nonkey_count(Da)
    unc, crit = split_critical(Da)
    rec["critical_minimal_fds"] = len(crit)
    ok, U = enforceable(Da)
    rec["enforceable"] = ok
    # 3NF synthesis with all minimal keys declared, BCNF whenever possible
    t1 = time.time()
    dec, is_bcnf_dec = synthesize_3nf_bcnf(F, Da)
    des = keyed(Da, dec)
    E = key_dependencies(n, des)
    rec["3nf_schemata"] = len(dec)
    rec["3nf_loss"] = loss_of(Da, E)
    crit_s = [S for S in dec if not is_bcnf(Da, S)]
    rec["3nf_critical"] = [(popcount(S), len(Da.restrict(S)), len(violators(Da, S))) for S in crit_s]
    rec["time_3nf"] = time.time() - t1
    rec["designs"] = {"3nf": design_json(n, Da, des, triggers=True),
                      "orig": design_json(n, Da, [(R, keys_R)], triggers=True)}
    # classical BCNF decomposition
    t1 = time.time()
    bdec = bcnf_decomposition(Da)
    bdes = keyed(Da, bdec)
    Eb = key_dependencies(n, bdes)
    rec["bcnf_schemata"] = len(bdec)
    rec["bcnf_loss"] = loss_of(Da, Eb)
    rec["bcnf_dp"] = all(Eb.implies(X, A) for (X, A) in Da.fds)
    try:
        rec["bcnf_sound"] = chase_lossless(n, bdec, Eb) if len(bdec) <= 40 else None
    except Exception:
        rec["bcnf_sound"] = None
    rec["time_bcnf"] = time.time() - t1
    rec["designs"]["bcnf"] = design_json(n, Da, bdes)
    # Repair
    t1 = time.time()
    rr = repair(n, F, Da=Da, local_time_limit=LOCAL_TIME, time_limit=DROP_TIME, max_w=MAX_W, max_extra=max_extra_for(n), ascend_time=ASCEND_TIME)
    rec["repair_mode"] = rr.mode
    rec["repair_loss"] = rr.loss
    rec["repair_exact"] = rr.exact
    rec["repair_schemata"] = None if rr.design is None else len(rr.design)
    rec["repair_local"] = [(popcount(S), r.loss, r.lower_bound, r.exact, r.heuristic, round(r.stats.get("time", 0), 1))
                           for S, r in rr.critical]
    rec["repair_local_lb_sum"] = sum(r.lower_bound for S, r in rr.critical) if rr.critical else 0
    rec["repair_stage"] = rr.stats.get("success_stage") or rr.stats.get("fallback_stage")
    rec["repair_candidates"] = rr.stats.get("success_candidates")
    rec["repair_ascend"] = {k: v for k, v in rr.stats.items() if k.startswith("ascend-")}
    rec["time_repair_ascend"] = rr.stats.get("time_ascend")
    if rr.mode == "fallback":
        rec["repair_fallback_lb"] = rr.stats.get("fallback_lower_bound")
        rec["repair_fallback_heuristic"] = rr.stats.get("fallback_heuristic")
        rec["repair_fallback_stage"] = rr.stats.get("fallback_stage")
        rec["repair_fallback_candidates"] = rr.stats.get("fallback_candidates")
        rec["time_repair_local"] = rr.stats.get("time_local")
    rec["time_repair"] = time.time() - t1
    if rr.design is not None:
        sound, local, Ea = check_bcnf_design(n, rr.design, Da)
        rec["repair_design_ok"] = bool(sound and local)
        rec["repair_loss_check"] = loss_of(Da, key_dependencies(n, rr.design))
        rec["designs"]["repair"] = design_json(n, Da, rr.design)
    # Drop on the whole schema
    if len(Da) <= DROP_MAX_MINIMAL:
        t1 = time.time()
        dr = drop(n, Da, time_limit=DROP_TIME, max_w=MAX_W, max_extra=max_extra_for(n), ascend_time=ASCEND_TIME)
        rec["drop_loss"] = dr.loss
        rec["drop_lb"] = dr.lower_bound
        rec["drop_exact"] = dr.exact
        rec["drop_heuristic"] = dr.heuristic
        rec["drop_delta_size"] = None if dr.delta is None else len(dr.delta)
        rec["drop_w_size"] = None if dr.W is None else len(dr.W)
        rec["drop_stats"] = {k: v for k, v in dr.stats.items() if k != "time"}
        if dr.design is not None:
            rec["designs"]["drop"] = design_json(n, Da, dr.design)
        rec["time_drop"] = time.time() - t1
    rec["time_total"] = time.time() - t0
    return rec

def table(rows):
    print("| FD set | n | FDs | minimal | keys | nu | lambda=0 | 3NF loss | critical (attrs, minimal FDs, violators) | BCNF loss (sound) | Repair loss [mode, local lb] | Drop loss [lb] | time |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        if "error" in r:
            print("| %s | %s | %s | error: %s |" % (r["name"], r.get("n"), r.get("fds"), r["error"][:80].replace("\n", " ")))
            continue
        rep = "%s [%s%s%s, lb %s%s]" % (r["repair_loss"], r["repair_mode"], "" if r["repair_exact"] else "*",
                                        "/" + r["repair_fallback_stage"] if r.get("repair_fallback_stage") else "",
                                        r.get("repair_fallback_lb", r["repair_local_lb_sum"]),
                                        ", greedy" if r.get("repair_fallback_heuristic") or any(x[4] for x in r["repair_local"]) else "")
        dr = "-" if "drop_loss" not in r else "%s [%s%s%s]" % (r["drop_loss"], r["drop_lb"], "" if r["drop_exact"] else "*",
                                                               ", greedy" if r["drop_heuristic"] else "")
        print("| %s | %d | %d | %d%s | %d | %d | %s | %d | %s | %d (%s) | %s | %s | %.0fs |" % (
            r["name"], r["n"], r["fds"], r["minimal_fds"], "+" if r.get("atomic_assumed") else "", r["keys"], r["nu"], "yes" if r["enforceable"] else "no",
            r["3nf_loss"], r["3nf_critical"], r["bcnf_loss"], r["bcnf_sound"], rep, dr, r["time_total"]))

def safe(name):
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in name)

def run_one(name):
    """run one FD set and write its record to results/e1_<name>.jsonl (used in a subprocess with a timeout)"""
    path = dict(SETS)[name]
    try:
        rec = run(name, path)
    except Exception:
        rec = {"name": name, "error": traceback.format_exc()[-600:]}
    with open(os.path.join("results", "e1_%s.jsonl" % safe(name)), "w", encoding="utf-8") as out:
        out.write(json.dumps(rec) + "\n")
    print("   ", {k: v for k, v in rec.items() if not k.startswith("time") and k not in ("drop_stats", "designs")}, flush=True)

def load_rows():
    rows = {}
    for name, _ in SETS:
        f = os.path.join("results", "e1_%s.jsonl" % safe(name))
        if os.path.isfile(f):
            for line in open(f, encoding="utf-8"):
                if line.strip():
                    rows[name] = json.loads(line)
    return [rows[name] for name, _ in SETS if name in rows]

def main():
    import subprocess
    args = sys.argv[1:]
    os.makedirs("results", exist_ok=True)
    if args[:1] == ["--one"]:
        run_one(args[1])
        return
    if args[:1] == ["--table"]:
        table(load_rows())
        return
    parallel = 1
    if args[:1] == ["--parallel"]:
        parallel = int(args[1])
        args = args[2:]
    flt = args[0] if args else None
    todo = [name for name, _ in SETS if not flt or flt in name]
    running = {}
    started = {}
    def launch(name):
        print("==", name, flush=True)
        started[name] = time.time()
        running[name] = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--one", name])
    while todo or running:
        while todo and len(running) < parallel:
            launch(todo.pop(0))
        time.sleep(2)
        for name, proc in list(running.items()):
            if proc.poll() is not None:
                print("    %s done in %.0fs" % (name, time.time() - started[name]), flush=True)
                del running[name]
            elif time.time() - started[name] > DATASET_TIMEOUT:
                proc.kill()
                with open(os.path.join("results", "e1_%s.jsonl" % safe(name)), "w", encoding="utf-8") as out:
                    out.write(json.dumps({"name": name, "error": "timeout after %d s" % DATASET_TIMEOUT}) + "\n")
                print("    %s timeout after %d s" % (name, DATASET_TIMEOUT), flush=True)
                del running[name]
    print()
    table(load_rows())

if __name__ == "__main__":
    main()
