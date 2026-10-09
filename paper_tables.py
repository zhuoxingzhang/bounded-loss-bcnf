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
        return "--" if not lb else r"$\geq$" + num(lb)
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

def table_e12(rows):
    """E1 and E2 in one full-width table: sizes, critical schemata, the losses of the five designs, running times"""
    out = []
    out.append(r"\begin{tabular}{lrrrrrrrrrrr}")
    out.append(r"\toprule")
    out.append(r"Data set & $|R|$ & $|\Da|$ & keys & crit. & $\nu$ & 3NF & BCNF & \repair & \drop & \repair\ (s) & \drop\ (s)\\")
    out.append(r"\midrule")
    for r in rows:
        if "error" in r:
            # a set that exceeded its budget: sizes from the FD file, the discovered FDs taken as the atomic cover
            import experiments
            from fdlib import load_any
            path = dict(experiments.SETS).get(r["name"])
            if path and r["error"].startswith("timeout"):
                n, F, _ = load_any(path)
                out.append(r"%s & %d & %s & \multicolumn{9}{l}{budget of four hours exceeded}\\" % (
                    tex_name(r["name"]), n, num(len(F.fds)) + "$^{+}$"))
            else:
                out.append(r"%s & \multicolumn{11}{l}{%s}\\" % (tex_name(r["name"]), r["error"][:40].replace("_", r"\_")))
            continue
        bcnf = num(r["bcnf_loss"]) + ("" if r.get("bcnf_sound") in (True, None) else r"$^{\dagger}$")
        out.append("%s & %d & %s & %s & %s & %s & %s & %s & %s & %s & %s & %s\\\\" % (
            tex_name(r["name"]), r["n"], num(r["minimal_fds"]) + ("$^{+}$" if r.get("atomic_assumed") else ""), num(r["keys"]),
            num(len(r.get("3nf_critical") or [])), num(r["nu"]), num(r["3nf_loss"]), bcnf, repair_cell(r), drop_cell(r),
            secs(r.get("time_repair")), secs(r.get("time_drop"))))
    out.append(r"\bottomrule")
    out.append(r"\end{tabular}")
    return "\n".join(out)

def secs(x):
    if x is None:
        return "--"
    return "%.1f" % x if x < 10 else "{:,.0f}".format(x)

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

E3_MODES = [("orig", r"original"), ("keys", r"keys only"), ("3nf", "3NF"), ("bcnf", "BCNF"), ("repair", r"\repair"), ("drop", r"\drop")]

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

E3_ORDER = [("orig", "original"), ("3nf", "3NF"), ("keys", "keys"), ("bcnf", "BCNF"), ("repair", r"\repair"), ("drop", r"\drop")]
E3_NAMES = {"fdred": "fd-red"}

def table_e3(e3recs, size=10000, budget=7200):
    """one row per data set: the trigger checks of the original relation and of 3NF synthesis, and the mean seconds
    (over the repetitions) for inserting `size` records into every design; a design equal to an earlier one shares
    its measurement, and a mode whose repetition the budget interrupted shows the budget as a lower bound"""
    out = [r"\begin{tabular}{lrrrrrrrr}", r"\toprule",
           r"Data set & \multicolumn{2}{c}{original} & \multicolumn{2}{c}{3NF} & keys & BCNF & \repair & \drop\\",
           r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}",
           r" & triggers & s & triggers & s & s & s & s & s\\",
           r"\midrule"]

    def cell(t):
        return "--" if t is None else ("%.1f" % t if t < 100 else "{:,.0f}".format(t))

    for name, recs in e3recs.items():
        cells = []
        for mode, _ in E3_ORDER:
            m = mode
            d, times, skipped = e3_summary(recs, m)
            if d is None and skipped and skipped.startswith("same design as "):
                m = skipped[len("same design as "):]
                d, times, _ = e3_summary(recs, m)
            if d is None:
                cells += ["--", "--"] if mode in ("orig", "3nf") else ["--"]
                continue
            t = times.get(size)
            if t is None and any(r.get("mode") == m and r.get("size") == size and "timeout_seconds" in r for r in recs):
                c = r"$>$" + "{:,}".format(budget)
            else:
                c = cell(t)
            if mode in ("orig", "3nf"):
                cells.append(num(d["fd_triggers"] + d["key_triggers"]))
            cells.append(c)
        label = tex_name(E3_NAMES.get(name, name.replace("tpch_", "tpch-")))
        out.append("%s & %s\\\\" % (label, " & ".join(cells)))
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)

E4_MODES = [("keys", "keys only"), ("3nf", "3NF"), ("bcnf", "BCNF"), ("repair", r"\repair"), ("drop", r"\drop")]

def load_e4():
    import e3
    out = {}
    for name in e3.SETS:
        f = os.path.join("results", "e4_%s.jsonl" % name)
        if os.path.isfile(f):
            out[name] = json.loads(open(f, encoding="utf-8").readline())
    return out

def table_e4(e4recs):
    """per data set: harmful updates and the integrity risk (per cent of harmful updates not caught) per design"""
    out = []
    out.append(r"\begin{tabular}{lrr" + "r" * len(E4_MODES) + "}")
    out.append(r"\toprule")
    out.append("Data set & rows & harmful & " + " & ".join(l for _, l in E4_MODES) + r"\\")
    out.append(r"\midrule")
    for name, r in e4recs.items():
        cells = []
        for mode, _ in E4_MODES:
            m = r["modes"].get(mode)
            cells.append("--" if m is None else "%.1f" % (100.0 * m["risk"]))
        out.append("%s & %s & %s & %s\\\\" % (tex_name(name.replace("tpch_", "tpch-")), num(r["rows"]), num(r["harmful"]), " & ".join(cells)))
    out.append(r"\bottomrule")
    out.append(r"\end{tabular}")
    return "\n".join(out)

TEASER_ORDER = ["D1+triggers", "3NF+trigger", "D1", "D2", "D4"]
TEASER_LABELS = {"D1+triggers": r"$\dec_1$, FDs by triggers", "3NF+trigger": r"3NF, $Z\rightarrow T$ by trigger",
                 "D1": r"$\dec_1$ (loss 2)", "D2": r"$\dec_2$ (loss 1)", "D4": r"$\dec_4$ (loss 1)"}

def fig_teaser(recs):
    """a pgfplots bar chart of the mean insertion time per design and number of records (results/teaser.jsonl)"""
    import statistics
    sizes = sorted(set(r["size"] for r in recs))
    out = [r"\begin{tikzpicture}",
           r"\begin{axis}[ybar, width=\columnwidth, height=4.2cm, bar width=4.5pt, enlarge x limits=0.25,",
           r"  ylabel={time (s)}, xlabel={records inserted}, symbolic x coords={%s}, xtick=data," % ",".join("{" + "{:,}".format(s) + "}" for s in sizes),
           r"  ymin=0, legend style={font=\scriptsize, at={(0.02,0.98)}, anchor=north west, legend columns=1, draw=none, fill=none},",
           r"  tick label style={font=\scriptsize}, label style={font=\scriptsize}, ymajorgrids]"]
    for d in TEASER_ORDER:
        pts = []
        for size in sizes:
            xs = [r["seconds"] for r in recs if r["design"] == d and r["size"] == size]
            if xs:
                pts.append("({" + "{:,}".format(size) + "}," + "{:.3f})".format(statistics.mean(xs)))
        out.append(r"\addplot coordinates {%s};" % " ".join(pts))
        out.append(r"\addlegendentry{%s}" % TEASER_LABELS[d])
    out.append(r"\end{axis}")
    out.append(r"\end{tikzpicture}")
    return "\n".join(out)

if __name__ == "__main__":
    rows = load_rows()
    os.makedirs("results", exist_ok=True)
    e3recs = load_e3()
    e4recs = load_e4()
    tf = os.path.join("results", "teaser.jsonl")
    teaser = [json.loads(l) for l in open(tf, encoding="utf-8") if l.strip()] if os.path.isfile(tf) else []
    for fn, t in (("table_e1.tex", table_e1(rows)), ("table_e2.tex", table_e2(rows)), ("table_e12.tex", table_e12(rows)), ("table_e3.tex", table_e3(e3recs)),
                  ("table_e4.tex", table_e4(e4recs)), ("fig_teaser.tex", fig_teaser(teaser) if teaser else "")):
        open(os.path.join("results", fn), "w", encoding="utf-8", newline="\n").write(t + "\n")
        print("==", fn)
        print(t)
