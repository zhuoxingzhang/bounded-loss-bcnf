r"""paper_tables.py: LaTeX tables for Section 6 from the records of experiments.py (E1, E2) and e3.py (E3).

usage: python paper_tables.py            writes results/table_e1.tex, table_e2.tex, table_e3.tex and prints them
"""
import os, json, sys, glob
from experiments import SETS, load_rows
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository root, which holds data/ and results/

NAMES = {"letter(non-dup)": "letter", "tpch-region": "region", "tpch-nation": "nation", "tpch-partsupp": "partsupp",
         "tpch-supplier": "supplier", "tpch-customer": "customer", "tpch-orders": "orders", "tpch-part": "part",
         "tpch-lineitem": "lineitem", "china_weather(null)": "weather",
         "doc-food+c1": "food", "doc-uk": "price paid", "doc-hospital": "hospital", "doc-tpcds": "TPC-DS"}   # the documented sets
# FD sets that the paper leaves out: the lineitem table of the HPI benchmark duplicates the TPC-H table lineitem; pdbx and
# the TPC-H tables other than lineitem have loss zero for 3NF synthesis and say nothing; diabetic and fd-red exceed the
# budget in 3NF synthesis already (2026-10-11, to save space)
EXCLUDE = {"lineitem", "pdbx(null)", "diabetic(null)", "fd-red", "tpch-region", "tpch-nation", "tpch-partsupp", "tpch-supplier",
           "tpch-customer", "tpch-orders", "tpch-part"}
# E3 and E4 sets that the paper leaves out (the runs exist): the TPC-H tables orders and part
E3_EXCLUDE = {"tpch_orders", "tpch_part"}

def paper_rows():
    """the E1 records of the FD sets that the paper reports, in the order of experiments.SETS"""
    return [r for r in load_rows() if r.get("name") not in EXCLUDE]

def tex_name(name):
    base = NAMES.get(name, name.replace("(null)", ""))
    return base.replace("_", r"\_")

def num(x):
    return "--" if x is None else ("{:,}".format(x) if isinstance(x, int) else str(x))

def value_of(cell):
    """the number that a cell shows, or None (a dash, or a lower bound such as $>$7,200)"""
    try:
        return float(cell.partition("$")[0].replace(",", "").replace(r"\best{", "").strip("}"))
    except ValueError:
        return None

def mark_best(cells, idx, ours=(), strict=False):
    r"""the cells with the least value among the positions idx set in \best; where one of our designs (positions
    ours) attains it, only ours are marked; with strict, a tie marks nothing (for comparing two variants)"""
    vals = {i: value_of(cells[i]) for i in idx}
    vals = {i: v for i, v in vals.items() if v is not None}
    if not vals:
        return cells
    b = min(vals.values())
    win = [i for i, v in vals.items() if v == b]
    if any(i in ours for i in win):
        win = [i for i in win if i in ours]
    if strict and len(win) > 1:
        return cells
    out = list(cells)
    for i in win:
        head, sep, tail = out[i].partition("$")
        out[i] = r"\best{%s}" % head + sep + tail
    return out

def whole_schema_lb(r):
    """the certified lower bound of the local search of Repair when 3NF synthesis returns R itself, so that the
    single critical schema is R and the local search is the global one"""
    loc = r.get("repair_local") or []
    if len(loc) == 1 and loc[0][0] == r.get("n"):
        return loc[0][2]
    return None

def repair_cell(r):
    """the loss of Repair; an asterisk unless it is proved minimal, by Repair itself or by the certified lower
    bound of Drop (the exact search of Drop or of the fallback of Repair)"""
    if "repair_loss" not in r or r["repair_loss"] is None:
        return "--"
    s = num(r["repair_loss"])
    lb = max(x for x in (r.get("drop_lb"), r.get("repair_fallback_lb"), whole_schema_lb(r), 0) if x is not None)
    if not r.get("repair_exact") and r["repair_loss"] > lb:
        s += r"$^{*}$"
    return s

def drop_cell(r):
    """the loss of Drop, with an asterisk unless it is proved minimal, by the exact search of Drop or by the certified
    lower bound (see bound_cell); a dash where Drop did not run"""
    if r.get("drop_loss") is None:
        return "--"
    lb = max(x for x in (r.get("drop_lb"), r.get("repair_fallback_lb"), whole_schema_lb(r), 0) if x is not None)
    return num(r["drop_loss"]) + ("" if r.get("drop_exact") or r["drop_loss"] <= lb else r"$^{*}$")

def bound_cell(r):
    """the certified lower bound on the loss: of the exact search of Drop, of the fallback of Repair, or of the
    local search of Repair when 3NF synthesis returns R itself (a loss is proved minimal iff it equals the bound)"""
    lbs = [x for x in (r.get("drop_lb"), r.get("repair_fallback_lb"), whole_schema_lb(r)) if x is not None]
    return num(max(lbs)) if lbs else "--"

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
            tex_name(r["name"]), r["n"], num(r["minimal_fds"]), num(r["keys"]), num(r["nu"]),
            num(r["3nf_loss"]), bcnf, repair_cell(r), drop_cell(r)))
    out.append(r"\bottomrule")
    out.append(r"\end{tabular}")
    return "\n".join(out)

def load_obstructions():
    """{set name: number of obstructions} from results/obstructions.jsonl (obstruction_stats.py)"""
    f = os.path.join(ROOT, "results", "obstructions.jsonl")
    out = {}
    if os.path.isfile(f):
        for l in open(f, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                if "obstructions" in r:
                    out[r["name"]] = r["obstructions"]
    return out

def load_gbcnf():
    """the greedy BCNF decomposition of gbcnf.py: name -> record"""
    out = {}
    for f in glob.glob(os.path.join(ROOT, "results", "gbcnf_*.jsonl")):
        for l in open(f, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                out[r["name"]] = r
    return out

def load_hybrid():
    """the Hybrid algorithm of Wei and Link (hybrid.py): name -> record"""
    out = {}
    for f in glob.glob(os.path.join(ROOT, "results", "hybrid_*.jsonl")):
        for l in open(f, encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                out[r["name"]] = r
    return out

def hybrid_cell(h):
    """the loss of Hybrid; a double dagger marks a run without data, whose levels come from the FDs alone"""
    if h is None:
        return "--"
    return num(h["hybrid_loss"]) + ("" if h.get("levels") == "data" else r"$^{\ddagger}$") + \
        ("" if h.get("hybrid_sound") in (True, None) else r"$^{\dagger}$")

def table_e12(rows, compact=True, records=None):
    """E1 and E2 in one full-width table: sizes, critical schemata of iCONF, the losses of the key-only design (nu),
    the obstruction design and the seven key designs with the certified lower bound, the numbers of schemata of iCONF
    and Repair, running times;
    compact leaves out the FD sets without a non-key FD (loss zero for every design) and those that exceeded the
    budget, which the text states in one sentence each; records maps FD set names to the numbers of records of
    the data sets loaded for E3 and E4, shown in a column after the name"""
    obstr = load_obstructions()
    greedy = load_gbcnf()
    hyb = load_hybrid()
    o = 1 if records is not None else 0
    cols = 19 + o
    out = []
    out.append(r"\begin{tabular}{l" + "r" * (cols - 1) + "}")
    out.append(r"\toprule")
    # the leading columns: data set, records (if any), |R|, |Sigma_a|, keys, crit.; then ten loss columns, two for the
    # schemata and two for the times
    out.append(" & ".join([""] * (5 + o) + [r"\multicolumn{10}{c}{dependency loss}", r"\multicolumn{2}{c}{schemata}", r"\multicolumn{2}{c}{time (s)}"]) + r"\\")
    out.append(r"\cmidrule(lr){%d-%d}\cmidrule(lr){%d-%d}\cmidrule(lr){%d-%d}" % (6 + o, 15 + o, 16 + o, 17 + o, 18 + o, 19 + o))
    out.append(" & ".join([""] * (7 + o) + [r"\multicolumn{2}{c}{3NF}", r"\multicolumn{2}{c}{BCNF}"] + [""] * 8) + r"\\")
    out.append(r"\cmidrule(lr){%d-%d}\cmidrule(lr){%d-%d}" % (8 + o, 9 + o, 10 + o, 11 + o))
    out.append(r"Data set & " + ("records & " if o else "") + r"$|R|$ & $|\Da|$ & keys & crit. & $\nu$ & $|\mathcal{O}|$ & iConf & classical & classical & greedy & Hybrid & \repair & \drop & bound"
               r" & 3NF & \repair & \repair & \drop\\")
    out.append(r"\midrule")
    for r in rows:
        if compact and ("error" in r or r.get("nu") == 0):
            continue
        if "error" in r:
            # a set that exceeded its budget: sizes from the FD file, the discovered FDs taken as the atomic cover
            import experiments
            from fdlib import load_any
            path = dict(experiments.SETS).get(r["name"])
            if path and r["error"].startswith("timeout"):
                n, F, _ = load_any(path)
                out.append(r"%s & %s%d & %s & \multicolumn{%d}{l}{budget of four hours exceeded}\\" % (
                    tex_name(r["name"]), "-- & " if o else "", n, num(len(F.fds)), cols - 3 - o))
            else:
                out.append(r"%s & \multicolumn{%d}{l}{%s}\\" % (tex_name(r["name"]), cols - 1, r["error"][:40].replace("_", r"\_")))
            continue
        bcnf = num(r["bcnf_loss"]) + ("" if r.get("bcnf_sound") in (True, None) else r"$^{\dagger}$")
        ob = obstr.get(r["name"])
        g = greedy.get(r["name"])
        gcell = "--" if g is None else num(g["gbcnf_loss"]) + ("" if g.get("gbcnf_sound") in (True, None) else r"$^{\dagger}$")
        rec = [] if not o else [num(records[r["name"]]) if records.get(r["name"]) else "--"]
        cells = [tex_name(r["name"])] + rec + [
            "%d" % r["n"], num(r["minimal_fds"]), num(r["keys"]),
            num(len(r.get("3nf_critical") or [])), num(r["nu"]), "--" if ob is None else num(ob), num(r["3nf_loss"]), num(r.get("3nfc_loss")),
            bcnf, gcell, hybrid_cell(hyb.get(r["name"])), repair_cell(r), drop_cell(r), bound_cell(r), num(r.get("3nf_schemata")), num(r.get("repair_schemata")),
            secs(r.get("time_repair")), secs(r.get("time_drop"))]
        # the least loss among the eight key designs (nu, iConf, classical 3NF, classical and greedy BCNF, Hybrid,
        # Repair, Drop; not the obstruction design inside Repair)
        cells = mark_best(cells, [5 + o] + list(range(7 + o, 14 + o)), ours=(12 + o, 13 + o))
        out.append(" & ".join(cells) + r"\\")
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

# ----------------------------------------------------------------------------- RQ3 and RQ4 on PostgreSQL
# the designs of E3 (e3pg.py modes) and E4 (e4.py modes), in the column order of the tables and figures
E3_ORDER = [("orig-x", "original"), ("3nf-x", "3NF (iConf)"), ("3nfc-x", "3NF (classical)"), ("keys", "keys"),
            ("bcnf", "BCNF"), ("gbcnf", "greedy"), ("repair", r"\repair"), ("drop", r"\drop")]
E3_NAMES = {"fdred": "fd-red", "pricepaid": "price paid", "tpcds": "TPC-DS"}

def documented_rule(name, done):
    """a rule before the first documented set (e3.DOCUMENTED) of a table, which follow the discovered ones"""
    import e3
    if name in e3.DOCUMENTED and not done:
        return [r"\midrule"], True
    return [], done

E4_MODES = [("keys", "keys only"), ("3nf", "3NF (iConf)"), ("3nfc", "3NF (classical)"), ("bcnf", "BCNF"), ("gbcnf", "greedy"),
            ("repair", r"\repair"), ("drop", r"\drop")]

def e3_label(name):
    return tex_name(E3_NAMES.get(name, name.replace("tpch_", "tpch-")))

def load_e3():
    """the PostgreSQL E3 records per set: {set: [records]} (results/e3pg_<set>.jsonl of e3pg.py)"""
    import e3
    out = {}
    for name in e3.SETS:
        f = os.path.join(ROOT, "results", "e3pg_%s.jsonl" % name)
        if os.path.isfile(f) and name not in E3_EXCLUDE:
            out[name] = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
    return out

def e3_summary(recs, mode):
    """the measurement of a mode: (design record, {size: [seconds of the completed repetitions]}, {size: elapsed
    seconds of a repetition that the budget cancelled}, sizes the budget skipped, the mode measured). A mode whose
    design repeats an earlier one shares that measurement, also when a later run found the repetition (e3pg.py
    --known); only the records after the last design record of the
    mode count, so that a rerun replaces an earlier run, unless the earlier run built the same design under the same
    protocol (a run resumed after the server closed the connection): then the repetitions of both
    runs are pooled. A reference to another mode means that mode as it was when the reference was written: a later
    run of the referred mode with another design does not change the measurement of the referring mode."""
    seen = set()
    lim = len(recs)
    while True:
        seen.add(mode)
        idx = [i for i, r in enumerate(recs[:lim]) if r.get("mode") == mode and r.get("design")]
        same = [(i, r["same_as"]) for i, r in enumerate(recs[:lim]) if r.get("mode") == mode and r.get("same_as")]
        if same and (not idx or same[-1][0] > idx[-1]):   # the latest run of the mode referred to another mode
            if same[-1][1] in seen:
                return None, {}, {}, set(), None
            lim, mode = same[-1]
            continue
        if idx:
            break
        return None, {}, {}, set(), None
    start = idx[-1]
    sig = lambda r: tuple(r.get(k) for k in ("loss", "rows", "copy", "schemata", "unique", "unique_md5", "exclusion",
                                             "trigger_fds", "indexes"))
    first = len(idx) - 1
    while first > 0 and sig(recs[idx[first - 1]]) == sig(recs[start]):
        first -= 1
    times, cancelled, skipped = {}, {}, set()
    for r in recs[idx[first] + 1:lim]:
        if r.get("mode") != mode or r.get("design"):
            continue
        if "seconds" in r:
            times.setdefault(r["size"], []).append(r["seconds"])
        elif "timeout_seconds" in r:
            cancelled[r["size"]] = r["timeout_seconds"]
        elif r.get("truncated") and "size" not in r:
            skipped.add(int(r["truncated"].rsplit(" ", 1)[1]))
    return recs[start], times, cancelled, skipped, mode

def e3_mean(recs, mode, size):
    """(mean, standard deviation, repetitions, cut by the budget) of the insertion of `size` records"""
    import statistics
    d, times, cancelled, skipped, _ = e3_summary(recs, mode)
    xs = times.get(size, [])
    cut = size in cancelled or size in skipped
    if not xs:
        return None, None, 0, cut
    return statistics.mean(xs), (statistics.stdev(xs) if len(xs) > 1 else 0.0), len(xs), cut

def load_e4():
    """the E4 records per set, one per seed: {set: [records]} (results/e4_<set>.jsonl of e4.py)"""
    import e3
    out = {}
    for name in e3.SETS:
        f = os.path.join(ROOT, "results", "e4_%s.jsonl" % name)
        if os.path.isfile(f) and name not in E3_EXCLUDE:
            out[name] = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
    return out

def e4_risk(recs, mode):
    """(mean, standard deviation) of the integrity risk in per cent over the seeds, or (None, None)"""
    import statistics
    xs = [100.0 * r["modes"][mode]["risk"] for r in recs if mode in r.get("modes", {})]
    if not xs:
        return None, None
    return statistics.mean(xs), (statistics.stdev(xs) if len(xs) > 1 else 0.0)

def e4_harmful(recs):
    import statistics
    return statistics.mean(r["harmful"] for r in recs)

def table_e3(e3recs, e4recs=None, size=10000, budget=7200, compact=False):
    """one row per data set: the exclusion constraints of the original relation and of the two 3NF syntheses, the
    mean seconds (over the repetitions) for inserting `size` records into every design, where a design equal to an
    earlier one shares its measurement and a design whose insertion the budget cancelled shows the budget as a lower
    bound, and the records of the data set and the mean number of harmful updates among its random updates (e4.py);
    a cell with fewer than five completed repetitions carries their number as a superscript; the compact variant
    for a single column leaves out the greedy decomposition, Drop and the records"""
    modes = [(m, l) for m, l in E3_ORDER if not compact or m not in ("gbcnf", "drop")]
    if compact:
        out = [r"\begin{tabular}{l" + "r" * 10 + "}", r"\toprule",
               r"Data set & \multicolumn{2}{c}{original} & \multicolumn{2}{c}{3NF (iConf)} & \multicolumn{2}{c}{3NF (classical)} & keys & BCNF & \repair & harmful\\",
               r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}",
               r" & excl. & s & excl. & s & excl. & s & s & s & s & updates\\",
               r"\midrule"]
    else:
        out = [r"\begin{tabular}{l" + "r" * 15 + "}", r"\toprule",
               r"Data set & \multicolumn{2}{c}{original} & \multicolumn{2}{c}{3NF (iConf)} & \multicolumn{2}{c}{3NF (classical)} & keys & BCNF & greedy & \repair & \drop & records & harmful\\",
               r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}\cmidrule(lr){6-7}",
               r" & excl. & s & excl. & s & excl. & s & s & s & s & s & s & & updates\\",
               r"\midrule"]

    def cell(t):
        return "--" if t is None else ("%.2f" % t if t < 10 else ("%.1f" % t if t < 100 else "{:,.0f}".format(t)))

    ruled = False
    for name, recs in e3recs.items():
        rule, ruled = documented_rule(name, ruled)
        out += rule
        cells = []
        for mode, _ in modes:
            d = e3_summary(recs, mode)[0]
            mean, sd, n, cut = e3_mean(recs, mode, size)
            c = (r"$>$" + "{:,}".format(budget)) if (mean is None and cut) else cell(mean)
            if mean is not None and 0 < n < 5:
                c += r"$^{%d}$" % n
            if mode.endswith("-x"):
                cells.append("--" if d is None else num(d["exclusion"]))
            cells.append(c)
        r4 = (e4recs or {}).get(name)
        if compact:
            cells.append("--" if not r4 else num(round(e4_harmful(r4))))
        else:
            cells += ["--", "--"] if not r4 else [num(r4[0]["rows"]), num(round(e4_harmful(r4)))]
        out.append("%s & %s\\\\" % (e3_label(name), " & ".join(cells)))
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)

def table_e4(e4recs):
    """per data set: rows, mean harmful updates and the mean integrity risk (per cent of harmful updates not caught)"""
    out = []
    out.append(r"\begin{tabular}{lrr" + "r" * len(E4_MODES) + "}")
    out.append(r"\toprule")
    out.append("Data set & rows & harmful & " + " & ".join(l for _, l in E4_MODES) + r"\\")
    out.append(r"\midrule")
    for name, recs in e4recs.items():
        cells = []
        for mode, _ in E4_MODES:
            m, _ = e4_risk(recs, mode)
            cells.append("--" if m is None else "%.1f" % m)
        out.append("%s & %s & %s & %s\\\\" % (e3_label(name), num(recs[0]["rows"]), num(round(e4_harmful(recs))), " & ".join(cells)))
    out.append(r"\bottomrule")
    out.append(r"\end{tabular}")
    return "\n".join(out)

def load_weighted():
    """the records of weighted.py per set: {set: record} (results/weighted_<set>.jsonl)"""
    import e3
    out = {}
    for name in e3.SETS:
        f = os.path.join(ROOT, "results", "weighted_%s.jsonl" % name)
        if os.path.isfile(f) and name not in E3_EXCLUDE:
            out[name] = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()][-1]
    return out

def load_drift(s=2.0, alpha=1.0):
    """the pooled integrity risk (per cent) of every design of drift.py over its permutations at the drifted workload
    (Zipf exponent s, mixture weight alpha; the defaults are the strongest drift, total variation 0.59 to 0.70 from
    the uniform choice): {set: {mode: risk}} from results/drift_<set>.jsonl"""
    out = {}
    for f in glob.glob(os.path.join(ROOT, "results", "drift_*.jsonl")):
        rs = [r for r in (json.loads(l) for l in open(f, encoding="utf-8") if l.strip()) if r["s"] == s and r["alpha"] == alpha]
        if rs:
            harm = sum(r["harmful"] for r in rs)
            out[rs[0]["set"]] = {m: 100.0 * sum(r["missed"][m] for r in rs) / max(harm, 1) for m in rs[0]["missed"]}
    return out

def table_weighted(wrecs, algs=("repair",), drift=None):
    """per data set: the unenforced minimal FDs and the mean integrity risk (per cent) of the algorithms under unit
    weights (the designs of E1) and under the weights of weighted.py, on the same evaluation updates, and, with drift
    (load_drift), the risk of the same designs under the drifted workload of drift.py; the paper shows Repair only,
    since Drop returns the same designs as Repair under these weights"""
    k = 6 if drift else 4
    if len(algs) == 1:
        out = [r"\begin{tabular}{l" + "r" * k + "}", r"\toprule",
               r"Data set & \multicolumn{2}{c}{$\loss$} & \multicolumn{2}{c}{risk (\%)}" + (r" & \multicolumn{2}{c}{drift (\%)}" if drift else "") + r"\\",
               r"\cmidrule(lr){2-3}\cmidrule(lr){4-5}" + (r"\cmidrule(lr){6-7}" if drift else ""),
               " & " + " & ".join([r"unit & $w$"] * (k // 2)) + r"\\",
               r"\midrule"]
    else:
        out = [r"\begin{tabular}{l" + "r" * (k * len(algs)) + "}", r"\toprule",
               r"Data set & " + " & ".join(r"\multicolumn{%d}{c}{\%s}" % (k, a) for a in algs) + r"\\",
               "".join(r"\cmidrule(lr){%d-%d}" % (2 + k * i, 1 + k * (i + 1)) for i in range(len(algs))),
               " & " + " & ".join([r"\multicolumn{2}{c}{$\loss$} & \multicolumn{2}{c}{risk (\%)}" + (r" & \multicolumn{2}{c}{drift (\%)}" if drift else "")] * len(algs)) + r"\\",
               " & " + " & ".join([" & ".join([r"unit & $w$"] * (k // 2))] * len(algs)) + r"\\",
               r"\midrule"]
    ruled = False
    for name, r in wrecs.items():
        rule, ruled = documented_rule(name, ruled)
        out += rule
        cells = []
        for alg in algs:
            ms = [r["modes"].get(alg), r["modes"].get(alg + "_w")]
            cells += ["--" if m is None else num(m["loss"]) for m in ms]
            cells += ["--" if m is None else "%.1f" % (100.0 * m["risk"]) for m in ms]
            if drift:
                d = drift.get(name, {})
                cells += ["--" if d.get(m) is None else "%.1f" % d[m] for m in (alg, alg + "_w")]
        out.append("%s & %s" % (e3_label(name), " & ".join(cells)) + "\\\\")
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)

TEASER_ORDER = ["D1+exclude", "3NF+exclude", "D1", "D2", "D4"]
TEASER_LABELS = {"D1+exclude": r"$\dec_1$, FDs by exclusion", "3NF+exclude": r"3NF, $Z\rightarrow T$ by exclusion",
                 "D1": r"$\dec_1$, keys only (loss 2)", "D2": r"$\dec_2$ (loss 1)", "D4": r"$\dec_4$ (loss 1)"}

def fig_teaser(recs):
    """a pgfplots bar chart of the mean insertion time per design and number of records (results/teaser_pg.jsonl of
    teaser_pg.py) on a logarithmic axis: the layout of figures/fig_teaser.tex, with two legend rows centred over the
    plot box"""
    import statistics
    sizes = sorted(set(r["size"] for r in recs))
    keys = {"D1+exclude": "d1x", "3NF+exclude": "3nfx", "D1": "d1", "D2": "d2", "D4": "d4"}
    out = [r"\begin{tikzpicture}",
           r"\begin{axis}[name=teaseraxis, ybar, width=\columnwidth, height=3.8cm, bar width=4.5pt, enlarge x limits=0.25,",
           r"  ylabel={time (s)}, xlabel={records inserted}, symbolic x coords={%s}, xtick=data," % ",".join("{" + "{:,}".format(s) + "}" for s in sizes),
           r"  ymode=log, log origin y=infty, ymin=0.08, ymax=20, log ticks with fixed point, tick pos=left,",
           r"  legend image code/.code={\draw[#1] (0cm,-0.07cm) rectangle (0.32cm,0.07cm);},",
           r"  tick label style={font=\scriptsize}, label style={font=\scriptsize}, ymajorgrids]"]
    for d in TEASER_ORDER:
        pts = []
        for size in sizes:
            xs = [r["seconds"] for r in recs if r["design"] == d and r["size"] == size]
            if xs:
                pts.append("({" + "{:,}".format(size) + "}," + "{:.3f})".format(statistics.mean(xs)))
        out.append(r"\addplot coordinates {%s};" % " ".join(pts))
        out.append(r"\label{plot:teaser-%s}" % keys[d])
    out.append(r"\end{axis}")
    out.append(r"% two legend rows, each centered over the plot box (the y label is not counted): the designs with exclusion constraints, then the designs with keys only")
    out.append(r"\node[anchor=south, font=\scriptsize, inner sep=1pt] at ([yshift=13pt]teaseraxis.north) {%s};" % r"\qquad".join(
        r"\ref{plot:teaser-%s}\,%s" % (keys[d], TEASER_LABELS[d]) for d in TEASER_ORDER[:2]))
    out.append(r"\node[anchor=south, font=\scriptsize, inner sep=1pt] at ([yshift=2pt]teaseraxis.north) {%s};" % r"\qquad".join(
        r"\ref{plot:teaser-%s}\,%s" % (keys[d], TEASER_LABELS[d]) for d in TEASER_ORDER[2:]))
    out.append(r"\end{tikzpicture}")
    return "\n".join(out)

if __name__ == "__main__":
    rows = paper_rows()
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    e3recs = load_e3()
    e4recs = load_e4()
    tf = os.path.join(ROOT, "results", "teaser_pg.jsonl")
    teaser = [json.loads(l) for l in open(tf, encoding="utf-8") if l.strip()] if os.path.isfile(tf) else []
    import e3
    records = {e3.SETS[n]: recs[0]["rows"] for n, recs in e4recs.items() if n in e3.SETS}
    for fn, t in (("table_e1.tex", table_e1(rows)), ("table_e2.tex", table_e2(rows)), ("table_e12.tex", table_e12(rows, records=records)),
                  ("table_e12_full.tex", table_e12(rows, compact=False, records=records)), ("table_e3.tex", table_e3(e3recs, e4recs, compact=True)),
                  ("table_e3_full.tex", table_e3(e3recs, e4recs)),
                  ("table_e4.tex", table_e4(e4recs)), ("table_weighted.tex", table_weighted(load_weighted(), drift=load_drift())),
                  ("table_weighted_full.tex", table_weighted(load_weighted(), ("repair", "drop"), drift=load_drift())),
                  ("fig_teaser.tex", fig_teaser(teaser) if teaser else "")):
        open(os.path.join(ROOT, "results", fn), "w", encoding="utf-8", newline="\n").write(t + "\n")
        print("==", fn)
        print(t)
