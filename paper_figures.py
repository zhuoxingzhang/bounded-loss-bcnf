r"""paper_figures.py: pgfplots bar charts for Section 6 from the records of experiments.py (RQ1), e3.py (RQ3) and
e4.py (RQ4): one full-width figure with three panels that share the colours of the designs.

usage: python paper_figures.py            writes results/fig_results.tex and prints it
"""
import os
from paper_tables import paper_rows, load_e3, e3_summary, load_e4, tex_name, E3_NAMES

# the designs in the order of the legend, with their colours (the same in every panel)
STYLES = [("orig", "original", "black, fill=black!25"),
          ("3nf", "3NF (iConf)", "red, fill=red!30"),
          ("keys", "keys only", "gray, fill=gray!45"),
          ("bcnf", "BCNF", "orange!80!black, fill=orange!45"),
          ("repair", r"\repair", "blue, fill=blue!30"),
          ("drop", r"\drop", "green!50!black, fill=green!40")]
STYLE = {k: s for k, _, s in STYLES}

def panel(title, ylabel, names, series, log, ymin, ymax=None, legend=False):
    """one ybar axis: names are the x labels, series a list of (design key, {name: value}); bars of value None are
    left out; log draws a logarithmic y axis; legend adds the legend of all designs to this panel"""
    out = [r"\nextgroupplot[ylabel={%s}, title={%s}, title style={font=\scriptsize, yshift=-3pt}," % (ylabel, title),
           r"  symbolic x coords={%s}, xtick=data, ymin=%s%s," % (",".join("{%s}" % n for n in names), ymin, "" if ymax is None else ", ymax=%s" % ymax),
           r"  %s]" % ("ymode=log, log origin=infty" if log else "ymode=normal")]
    if legend:
        for key, label, style in STYLES:
            out.append(r"\addlegendimage{%s}\addlegendentry{%s}" % (style, label))
    for key, vals in series:
        pts = " ".join("({%s},%s)" % (n, v) for n, v in ((n, vals.get(n)) for n in names) if v is not None)
        out.append(r"\addplot[%s] coordinates {%s};" % (STYLE[key], pts))
    return out

def fig_results(rows, e3recs, e4recs, size=10000, budget=7200):
    # RQ1: the losses of the five designs on the FD sets with positive loss
    loss_rows = [r for r in rows if "error" not in r and (r.get("repair_loss") or 0) > 0]
    names1 = [tex_name(r["name"]) for r in loss_rows]
    loss = {}
    for key, field in (("keys", "nu"), ("3nf", "3nf_loss"), ("bcnf", "bcnf_loss"), ("repair", "repair_loss"), ("drop", "drop_loss")):
        loss[key] = {tex_name(r["name"]): r.get(field) for r in loss_rows if r.get(field)}
    # RQ3: the mean time for inserting `size` records; interrupted runs at the budget
    names3, time = [], {k: {} for k, _, _ in STYLES}
    for name, recs in e3recs.items():
        label = tex_name(E3_NAMES.get(name, name.replace("tpch_", "tpch-")))
        names3.append(label)
        for key, _, _ in STYLES:
            m = key
            d, times, skipped = e3_summary(recs, m)
            if d is None and skipped and skipped.startswith("same design as "):
                m = skipped[len("same design as "):]
                d, times, _ = e3_summary(recs, m)
            if d is None:
                continue
            t = times.get(size)
            if t is None and any(r.get("mode") == m and r.get("size") == size and "timeout_seconds" in r for r in recs):
                t = budget
            if t is not None:
                time[key][label] = "%.3f" % t
    # RQ4: the integrity risk in per cent
    names4, risk = [], {k: {} for k, _, _ in STYLES}
    for name, r in e4recs.items():
        label = tex_name(name.replace("tpch_", "tpch-"))
        names4.append(label)
        for key in ("keys", "3nf", "bcnf", "repair", "drop"):
            m = r["modes"].get(key)
            if m is not None:
                risk[key][label] = "%.1f" % (100.0 * m["risk"])
    out = [r"\begin{tikzpicture}",
           r"\begin{groupplot}[group style={group size=1 by 3, vertical sep=36pt}, ybar, width=\textwidth, height=3.6cm,",
           r"  /pgf/bar width=2.6pt, enlarge x limits=0.06, ymajorgrids, tick label style={font=\scriptsize}, label style={font=\scriptsize},",
           r"  xticklabel style={font=\scriptsize},",
           r"  legend style={font=\scriptsize, at={(0.5,1.18)}, anchor=south, legend columns=-1, draw=none, fill=none, /tikz/every even column/.append style={column sep=6pt}},",
           r"  legend image code/.code={\draw[#1] (0cm,-0.07cm) rectangle (0.32cm,0.07cm);}]"]
    out += panel("(a) dependency loss (RQ1)", "minimal FDs", names1,
                 [(k, loss[k]) for k in ("keys", "3nf", "bcnf", "repair", "drop")], True, 1, legend=True)
    out += panel("(b) time for inserting 10,000 records (RQ3)", "seconds", names3,
                 [(k, time[k]) for k in ("orig", "3nf", "keys", "bcnf", "repair", "drop")], True, 0.1, 20000)
    out += panel("(c) integrity risk (RQ4)", "per cent", names4,
                 [(k, risk[k]) for k in ("keys", "3nf", "bcnf", "repair", "drop")], False, 0, 100)
    out += [r"\end{groupplot}", r"\end{tikzpicture}"]
    return "\n".join(out)

if __name__ == "__main__":
    rows = paper_rows()
    t = fig_results(rows, load_e3(), load_e4())
    open(os.path.join("results", "fig_results.tex"), "w", encoding="utf-8", newline="\n").write(t + "\n")
    print(t)
