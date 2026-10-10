r"""paper_figures.py: pgfplots bar charts for Section 6 from the records of experiments.py and gbcnf.py (RQ1), e3pg.py
(RQ3, PostgreSQL) and e4.py (RQ4): one full-width figure with three panels that share the colours of the designs.

Every design keeps its bar position in every panel (explicit bar shifts), so that a design that a panel does not show
leaves a gap rather than moving the others. An insertion that the budget cancelled is drawn at the budget with a
hatched bar, a value of zero on a logarithmic axis by a circle at the bottom, and a missing value by a cross there.
The figure needs \usetikzlibrary{patterns}.

usage: python paper_figures.py            writes results/fig_results.tex and prints it
"""
import os
from paper_tables import paper_rows, load_e3, e3_mean, load_e4, e4_risk, load_gbcnf, tex_name, e3_label

# the designs in the order of the legend and of the bars, with their colours (the same in every panel)
STYLES = [("orig", "original", "black, fill=black!25"),
          ("3nf", "3NF (iConf)", "red, fill=red!30"),
          ("3nfc", "3NF (classical)", "red!50!black, fill=red!10"),
          ("keys", "keys only", "gray, fill=gray!45"),
          ("bcnf", "BCNF", "orange!80!black, fill=orange!45"),
          ("gbcnf", "BCNF (greedy)", "brown!80!black, fill=yellow!40"),
          ("repair", r"\repair", "blue, fill=blue!30"),
          ("drop", r"\drop", "green!50!black, fill=green!40")]
STYLE = {k: s for k, _, s in STYLES}
E3_MODE = {"orig": "orig-x", "3nf": "3nf-x", "3nfc": "3nfc-x"}   # design key -> e3pg.py mode
BAR = 2.4    # bar width in pt
GAP = 0.3    # gap between the bars of a group in pt

def shift(key):
    i = [k for k, _, _ in STYLES].index(key)
    return (i - (len(STYLES) - 1) / 2.0) * (BAR + GAP)

def panel(title, ylabel, names, series, log, ymin, ymax=None, legend=False, hatched=None, floor=None):
    """one ybar axis: names are the x labels, series a list of (design key, {name: value}) with value None for a
    missing value; hatched maps design keys to the names whose bar was cut by the budget; on a logarithmic axis,
    floor is the y value at which zeros (circles) and missing values (crosses) are marked"""
    out = [r"\nextgroupplot[ylabel={%s}, title={%s}, title style={font=\scriptsize, yshift=-3pt}," % (ylabel, title),
           r"  symbolic x coords={%s}, xtick=data, ymin=%s%s," % (",".join("{%s}" % n for n in names), ymin, "" if ymax is None else ", ymax=%s" % ymax),
           r"  %s]" % ("ymode=log, log origin=infty" if log else "ymode=normal")]
    if legend:
        for key, label, style in STYLES:
            out.append(r"\addlegendimage{%s}\addlegendentry{%s}" % (style, label))
    for key, vals in series:
        sh = "bar shift=%.2fpt" % shift(key)
        cut = (hatched or {}).get(key, set())
        pts = " ".join("({%s},%s)" % (n, vals[n]) for n in names if vals.get(n) not in (None, 0) and n not in cut)
        if pts:
            out.append(r"\addplot[%s, %s, forget plot] coordinates {%s};" % (STYLE[key], sh, pts))
        pts = " ".join("({%s},%s)" % (n, vals[n]) for n in names if n in cut and vals.get(n) is not None)
        if pts:
            out.append(r"\addplot[%s, %s, forget plot, postaction={pattern=north east lines}] coordinates {%s};" % (STYLE[key], sh, pts))
        if floor is not None:
            for mark, pick in (("o", lambda n: vals.get(n) == 0), ("x", lambda n: n in vals and vals[n] is None)):
                pts = " ".join("({%s},%s)" % (n, floor) for n in names if pick(n))
                if pts:
                    out.append(r"\addplot[only marks, mark=%s, mark size=1.2pt, %s, xshift=%.2fpt, forget plot] coordinates {%s};" % (
                        mark, STYLE[key].split(",")[0], shift(key), pts))
    return out

def fig_results(rows, e3recs, e4recs, size=10000, budget=7200):
    greedy = load_gbcnf()
    # RQ1: the losses of the designs on the FD sets with positive loss
    loss_rows = [r for r in rows if "error" not in r and (r.get("repair_loss") or 0) > 0]
    names1 = [tex_name(r["name"]) for r in loss_rows]
    loss = {}
    for key, field in (("keys", "nu"), ("3nf", "3nf_loss"), ("3nfc", "3nfc_loss"), ("bcnf", "bcnf_loss"), ("repair", "repair_loss"), ("drop", "drop_loss")):
        loss[key] = {tex_name(r["name"]): r.get(field) for r in loss_rows}
    loss["gbcnf"] = {tex_name(r["name"]): (greedy[r["name"]]["gbcnf_loss"] if r["name"] in greedy else None) for r in loss_rows}
    # RQ3: the mean time for inserting `size` records; cancelled insertions at the budget, hatched
    names3, time, cut = [], {k: {} for k, _, _ in STYLES}, {k: set() for k, _, _ in STYLES}
    for name, recs in e3recs.items():
        label = e3_label(name)
        names3.append(label)
        for key, _, _ in STYLES:
            mean, sd, n, c = e3_mean(recs, E3_MODE.get(key, key), size)
            if mean is not None:
                time[key][label] = "%.3f" % mean
            elif c:
                time[key][label] = budget
                cut[key].add(label)
    # RQ4: the mean integrity risk in per cent over the seeds
    names4, risk = [], {k: {} for k, _, _ in STYLES}
    for name, recs in e4recs.items():
        label = e3_label(name)
        names4.append(label)
        for key in ("keys", "3nf", "3nfc", "bcnf", "gbcnf", "repair", "drop"):
            m, _ = e4_risk(recs, key)
            risk[key][label] = None if m is None else (0 if m == 0 else "%.2f" % m)
    out = [r"\begin{tikzpicture}",
           r"\begin{groupplot}[group style={group size=1 by 3, vertical sep=36pt}, ybar, width=\textwidth, height=3.6cm,",
           r"  /pgf/bar width=%.1fpt, enlarge x limits=0.06, ymajorgrids, tick pos=left, tick label style={font=\scriptsize}, label style={font=\scriptsize}," % BAR,
           r"  xticklabel style={font=\scriptsize}, log ticks with fixed point,",
           r"  legend style={font=\scriptsize, at={(0.5,1.18)}, anchor=south, legend columns=-1, draw=none, fill=none, /tikz/every even column/.append style={column sep=6pt}},",
           r"  legend image code/.code={\draw[#1] (0cm,-0.07cm) rectangle (0.32cm,0.07cm);}]"]
    out += panel("(a) dependency loss (RQ1)", "minimal FDs", names1,
                 [(k, loss[k]) for k in ("keys", "3nf", "3nfc", "bcnf", "gbcnf", "repair", "drop")], True, 1, legend=True, floor=1)
    out += panel("(b) time for inserting 10,000 records (RQ3)", "seconds", names3,
                 [(k, time[k]) for k, _, _ in STYLES], True, 0.1, 20000, hatched=cut)
    out += panel("(c) integrity risk (RQ4)", "per cent", names4,
                 [(k, risk[k]) for k in ("keys", "3nf", "3nfc", "bcnf", "gbcnf", "repair", "drop")], True, 0.1, 100, floor=0.1)
    out += [r"\end{groupplot}", r"\end{tikzpicture}"]
    return "\n".join(out)

if __name__ == "__main__":
    rows = paper_rows()
    t = fig_results(rows, load_e3(), load_e4())
    open(os.path.join("results", "fig_results.tex"), "w", encoding="utf-8", newline="\n").write(t + "\n")
    print(t)
