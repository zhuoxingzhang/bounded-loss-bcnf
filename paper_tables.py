r"""paper_tables.py: LaTeX tables for Section 6 from the records of experiments.py (E1, E2) and e3.py (E3).

usage: python paper_tables.py            writes results/table_e1.tex, table_e2.tex, table_e3.tex and prints them
"""
import os, json, sys
from experiments import SETS, load_rows

NAMES = {"letter(non-dup)": "letter", "tpch-region": "region", "tpch-nation": "nation", "tpch-partsupp": "partsupp",
         "tpch-supplier": "supplier", "tpch-customer": "customer", "tpch-orders": "orders", "tpch-part": "part",
         "tpch-lineitem": "lineitem (TPC-H)", "china_weather(null)": "weather"}

def tex_name(name):
    base = NAMES.get(name, name.replace("(null)", ""))
    return base.replace("_", r"\_")

def num(x):
    return "--" if x is None else ("{:,}".format(x) if isinstance(x, int) else str(x))

def repair_cell(r):
    if "repair_loss" not in r or r["repair_loss"] is None:
        return "--"
    s = num(r["repair_loss"])
    if not r.get("repair_exact"):
        s += r"$^{*}$"
    return s

def drop_cell(r):
    if r.get("drop_loss") is None:
        lb = r.get("drop_lb")
        if lb is None and r.get("repair_fallback_lb") is not None:
            lb = r["repair_fallback_lb"]
        return "--" if lb is None else r"$\geq$" + num(lb)
    s = num(r["drop_loss"])
    if not r.get("drop_exact"):
        s += r"$^{*}$ ($\geq$%s)" % num(r.get("drop_lb"))
    return s

def table_e1(rows):
    out = []
    out.append(r"\begin{tabular}{lrrrrrrrrr}")
    out.append(r"\toprule")
    out.append(r"Data set & $|R|$ & $|\Da|$ & keys & $\nu$ & 3NF & BCNF & \repair & \drop\\")
    out.append(r"\midrule")
    for r in rows:
        if "error" in r:
            out.append(r"%s & \multicolumn{8}{l}{%s}\\" % (tex_name(r["name"]), r["error"][:40].replace("_", r"\_")))
            continue
        bcnf = num(r["bcnf_loss"]) + ("" if r.get("bcnf_sound") in (True, None) else r"$^{\dagger}$")
        out.append("%s & %d & %s & %s & %s & %s & %s & %s & %s\\\\" % (
            tex_name(r["name"]), r["n"], num(r["minimal_fds"]) + ("$^{+}$" if r.get("atomic_assumed") else ""), num(r["keys"]), num(r["nu"]),
            num(r["3nf_loss"]), bcnf, repair_cell(r), drop_cell(r)))
    out.append(r"\bottomrule")
    out.append(r"\end{tabular}")
    return "\n".join(out)

def secs(x):
    if x is None:
        return "--"
    return "%.1f" % x if x < 10 else "%.0f" % x

def table_e2(rows):
    out = []
    out.append(r"\begin{tabular}{lrrrrrrr}")
    out.append(r"\toprule")
    out.append(r"Data set & critical & \repair\ (s) & mode & \drop\ (s) & $|\Delta|$ & $|W|$ & exact\\")
    out.append(r"\midrule")
    for r in rows:
        if "error" in r:
            continue
        crit = r.get("3nf_critical") or []
        mode = r.get("repair_mode", "--")
        if r.get("repair_fallback_stage"):
            mode += "/" + r["repair_fallback_stage"]
        ds = r.get("drop_stats") or {}
        exact = "yes" if r.get("drop_exact") else ("--" if r.get("drop_loss") is None else "no")
        out.append("%s & %d & %s & %s & %s & %s & %s & %s\\\\" % (
            tex_name(r["name"]), len(crit), secs(r.get("time_repair")), mode.replace("_", r"\_"), secs(r.get("time_drop")),
            num(r.get("drop_delta_size")), num(r.get("drop_w_size")), exact))
    out.append(r"\bottomrule")
    out.append(r"\end{tabular}")
    return "\n".join(out)

E3_MODES = [("orig", r"original"), ("3nf", "3NF"), ("bcnf", "BCNF"), ("repair", r"\repair"), ("drop", r"\drop")]

def load_e3():
    """the E3 records per set: {set: [records]} (results/e3_<set>.jsonl)"""
    import e3
    out = {}
    for name in e3.SETS:
        f = os.path.join("results", "e3_%s.jsonl" % name)
        if os.path.isfile(f):
            out[name] = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
    return out

def e3_summary(recs, mode):
    """(design record, {size: mean seconds}, skipped-or-None) of a mode"""
    import statistics
    sk = [r for r in recs if r.get("mode") == mode and r.get("skipped")]
    des = [r for r in recs if r.get("mode") == mode and r.get("design")]
    if not des:
        return None, {}, (sk[-1]["skipped"] if sk else None)
    times = {}
    for size in sorted(set(r["size"] for r in recs if r.get("mode") == mode and "seconds" in r)):
        xs = [r["seconds"] for r in recs if r.get("mode") == mode and r.get("size") == size and "seconds" in r]
        times[size] = statistics.mean(xs)
    return des[-1], times, None

def table_e3(e3recs, size=30000):
    """one row per data set and design: loss, schemata, UNIQUE indexes, trigger checks, seconds for `size`
    records (mean over the repetitions) and milliseconds per record"""
    out = []
    out.append(r"\begin{tabular}{llrrrrrr}")
    out.append(r"\toprule")
    out.append(r"Data set & design & loss & schemata & UNIQUE & triggers & time (s) & ms/record\\")
    out.append(r"\midrule")
    for name, recs in e3recs.items():
        first = True
        for mode, label in E3_MODES:
            d, times, skipped = e3_summary(recs, mode)
            if d is None:
                if skipped and skipped.startswith("same design"):
                    continue
                continue
            t = times.get(size)
            cell = "--" if t is None else ("%.1f" % t if t < 100 else "{:,.0f}".format(t))
            per = "--" if t is None else "%.3f" % (1000.0 * t / size)
            out.append("%s & %s & %s & %s & %s & %s & %s & %s\\\\" % (
                name.replace("_", r"\_") if first else "", label, num(d.get("loss")), num(d["schemata"]), num(d["unique"]),
                num(d["fd_triggers"] + d["key_triggers"]), cell, per))
            first = False
    out.append(r"\bottomrule")
    out.append(r"\end{tabular}")
    return "\n".join(out)

if __name__ == "__main__":
    rows = load_rows()
    os.makedirs("results", exist_ok=True)
    e3recs = load_e3()
    for fn, t in (("table_e1.tex", table_e1(rows)), ("table_e2.tex", table_e2(rows)), ("table_e3.tex", table_e3(e3recs))):
        open(os.path.join("results", fn), "w", encoding="utf-8", newline="\n").write(t + "\n")
        print("==", fn)
        print(t)
