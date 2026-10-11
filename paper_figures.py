r"""paper_figures.py: pgfplots bar charts for Section 6 from the records of experiments.py and gbcnf.py (RQ1), e3pg.py
(RQ3, PostgreSQL) and e4.py (RQ4): one full-width figure with three panels that share the colours of the designs.

Every design keeps its bar position in every panel (explicit bar shifts), so that a design that a panel does not show
leaves a gap rather than moving the others. An insertion that the budget cancelled is drawn at the budget with a
hatched bar, a value of zero on a logarithmic axis by a circle at the bottom, and a missing value by a cross there.
The figure needs \usetikzlibrary{patterns}.

The Pareto figure plots, per data set, the time for inserting 10,000 records (e3pg.py) against the integrity risk
(e4.py) of the same designs, including the two 3NF syntheses both with their non-key FDs enforced by exclusion
constraints (risk zero) and with keys only (e3pg.py modes 3nf and 3nfc), with the staircase of the Pareto front.

usage: python paper_figures.py            writes results/fig_results.tex (printed) and results/fig_pareto.tex
"""
import os
from paper_tables import paper_rows, load_e3, e3_mean, e3_estimated, load_e4, e4_risk, load_gbcnf, tex_name, e3_label

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

def panel(title, ylabel, names, series, log, ymin, ymax=None, legend=False, hatched=None, floor=None, dotted=None):
    """one ybar axis: names are the x labels, series a list of (design key, {name: value}) with value None for a
    missing value; hatched maps design keys to the names whose bar was cut by the budget, dotted those whose value is
    a placeholder estimate; on a logarithmic axis, floor is the y value at which zeros (circles) and missing values
    (crosses) are marked"""
    out = [r"\nextgroupplot[ylabel={%s}, title={%s}, title style={font=\scriptsize, yshift=-3pt}," % (ylabel, title),
           r"  symbolic x coords={%s}, xtick=data, ymin=%s%s," % (",".join("{%s}" % n for n in names), ymin, "" if ymax is None else ", ymax=%s" % ymax),
           r"  %s]" % ("ymode=log, log origin=infty" if log else "ymode=normal")]
    if legend:
        for key, label, style in STYLES:
            out.append(r"\addlegendimage{%s}\addlegendentry{%s}" % (style, label))
    for key, vals in series:
        sh = "bar shift=%.2fpt" % shift(key)
        cut = (hatched or {}).get(key, set())
        dot = (dotted or {}).get(key, set())
        pts = " ".join("({%s},%s)" % (n, vals[n]) for n in names if vals.get(n) not in (None, 0) and n not in cut and n not in dot)
        if pts:
            out.append(r"\addplot[%s, %s, forget plot] coordinates {%s};" % (STYLE[key], sh, pts))
        pts = " ".join("({%s},%s)" % (n, vals[n]) for n in names if n in cut and vals.get(n) is not None)
        if pts:
            out.append(r"\addplot[%s, %s, forget plot, postaction={pattern=north east lines}] coordinates {%s};" % (STYLE[key], sh, pts))
        pts = " ".join("({%s},%s)" % (n, vals[n]) for n in names if n in dot and n not in cut and vals.get(n) is not None)
        if pts:
            out.append(r"\addplot[%s, %s, forget plot, postaction={pattern=dots}] coordinates {%s};" % (STYLE[key], sh, pts))
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
    names3, time, cut, dot = [], {k: {} for k, _, _ in STYLES}, {k: set() for k, _, _ in STYLES}, {k: set() for k, _, _ in STYLES}
    for name, recs in e3recs.items():
        label = e3_label(name)
        names3.append(label)
        for key, _, _ in STYLES:
            mean, sd, n, c = e3_mean(recs, E3_MODE.get(key, key), size)
            if mean is not None:
                time[key][label] = "%.3f" % mean
                if e3_estimated(recs, E3_MODE.get(key, key), size):
                    dot[key].add(label)
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
                 [(k, time[k]) for k, _, _ in STYLES], True, 0.1, 20000, hatched=cut, dotted=dot)
    out += panel("(c) integrity risk (RQ4)", "per cent", names4,
                 [(k, risk[k]) for k in ("keys", "3nf", "3nfc", "bcnf", "gbcnf", "repair", "drop")], True, 0.1, 100, floor=0.1)
    out += [r"\end{groupplot}", r"\end{tikzpicture}"]
    return "\n".join(out)

# the designs of the Pareto figure: (e3pg.py mode, e4.py mode or None for the designs that enforce every FD and
# have risk zero, legend label, mark style); the 3NF syntheses appear twice, with their non-key FDs enforced by
# exclusion constraints (filled) and left to the application (hollow)
PARETO = [("orig-x", None, "original, FDs by exclusion", "black, mark=square*"),
          ("3nf-x", None, "3NF (iConf), FDs by exclusion", "red, mark=triangle*"),
          ("3nfc-x", None, "3NF (classical), FDs by exclusion", "red!50!black, mark=triangle*"),
          ("keys", "keys", "keys only", "gray, mark=*"),
          ("3nf", "3nf", "3NF (iConf), keys only", "red, mark=triangle, mark options={fill=white}"),
          ("3nfc", "3nfc", "3NF (classical), keys only", "red!50!black, mark=triangle, mark options={fill=white}"),
          ("bcnf", "bcnf", "BCNF", "orange!80!black, mark=diamond*"),
          ("gbcnf", "gbcnf", "BCNF (greedy)", "brown!80!black, mark=diamond, mark options={fill=white}"),
          ("repair", "repair", r"\repair", "blue, mark=pentagon*"),
          ("drop", "drop", r"\drop", "green!50!black, mark=star, mark size=2.4pt")]

def pareto_points(e3recs, e4recs, size=10000, budget=7200):
    """{set label: [(design index, seconds, risk in per cent, cut by the budget, estimated)]}: the mean time for
    inserting `size` records against the mean integrity risk; a design whose insertion the budget cancelled sits at
    the budget, and a placeholder estimate is flagged"""
    out = {}
    for name, recs in e3recs.items():
        r4 = e4recs.get(name)
        if not r4:
            continue
        pts = []
        for i, (m3, m4, _, _) in enumerate(PARETO):
            mean, sd, n, cut = e3_mean(recs, m3, size)
            if mean is None and not cut:
                continue
            risk = 0.0 if m4 is None else e4_risk(r4, m4)[0]
            if risk is None:
                continue
            pts.append((i, budget if mean is None else mean, risk, mean is None, e3_estimated(recs, m3, size)))
        out[e3_label(name)] = pts
    return out

def pareto_front(pts):
    """the points that no other point beats in time and risk, in increasing order of time"""
    front = []
    for p in sorted(pts, key=lambda p: (p[1], p[2])):
        if not front or p[2] < front[-1][2]:
            front.append(p)
    return front

def log_ticks(lo, hi):
    """tick values for a logarithmic axis from lo to hi: powers of ten over wide ranges, 1-2-5 steps otherwise"""
    import math
    steps = (1,) if hi / lo > 30 else (1, 2, 5)
    ticks = [m * 10 ** e for e in range(math.floor(math.log10(lo)) - 1, math.ceil(math.log10(hi)) + 1) for m in steps]
    ticks = [t for t in ticks if lo / 1.3 <= t <= hi * 1.3]
    return ticks if len(ticks) >= 2 else [10 ** math.floor(math.log10(lo)), 10 ** math.ceil(math.log10(hi))]

def fig_pareto(e3recs, e4recs, size=10000, budget=7200, cols=4):
    """small multiples, one per data set: insertion time (logarithmic) against integrity risk, with the staircase of
    the Pareto front; the legend is a named legend that the figure places above the plots"""
    data = pareto_points(e3recs, e4recs, size, budget)
    names = list(data)
    rows = -(-(len(names) + 1) // cols)
    out = [r"\begin{tikzpicture}",
           r"\begin{groupplot}[group style={group size=%d by %d, horizontal sep=26pt, vertical sep=30pt, xlabels at=edge bottom, ylabels at=edge left}," % (cols, rows),
           r"  width=4.9cm, height=3.6cm, xmode=log, ymin=-6, ymax=106, ytick={0,25,50,75,100}, log ticks with fixed point,",
           r"  xlabel={seconds for %s records}, ylabel={risk (\%%)}, tick label style={font=\tiny}, label style={font=\scriptsize}," % "{:,}".format(size),
           r"  title style={font=\scriptsize, yshift=-4pt}, every axis plot/.append style={mark size=1.8pt}, ymajorgrids, tick pos=left, enlarge x limits=0.12]"]
    for k, name in enumerate(names):
        opts = ["title={%s}" % name]
        xs = [p[1] for p in data[name]]
        if xs:
            opts.append("xtick={%s}" % ",".join("%g" % t for t in log_ticks(min(xs), max(xs))))
        if k == 0:
            opts.append(r"legend to name=paretolegend, legend columns=5, legend cell align=left, legend style={font=\scriptsize, draw=none, /tikz/every even column/.append style={column sep=8pt}}")
        out.append(r"\nextgroupplot[%s]" % ", ".join(opts))
        if k == 0:
            for _, _, label, style in PARETO:
                out.append(r"\addlegendimage{only marks, %s}\addlegendentry{%s}" % (style, label))
        front = pareto_front(data[name])
        if len(front) > 1:
            out.append(r"\addplot[const plot, gray!70, forget plot] coordinates {%s};" % " ".join("(%.4g,%.4g)" % (p[1], p[2]) for p in front))
        for i, x, y, cut, estimated in data[name]:
            style = PARETO[i][3] + (", opacity=0.4" if estimated else "")
            out.append(r"\addplot[only marks, %s, forget plot] coordinates {(%.4g,%.4g)};" % (style, x, y))
            if cut:
                out.append(r"\node[font=\tiny, anchor=south] at (axis cs:%.4g,%.4g) {$>$};" % (x, y))
    out += [r"\end{groupplot}",
            r"\node[anchor=south] at ([yshift=14pt]group c%dr1.north east) {\ref{paretolegend}};" % (cols // 2) if cols % 2 == 0 else
            r"\node[anchor=south] at ([yshift=14pt]group c%dr1.north) {\ref{paretolegend}};" % (cols // 2 + 1),
            r"\end{tikzpicture}"]
    return "\n".join(out)

if __name__ == "__main__":
    rows = paper_rows()
    e3recs, e4recs = load_e3(), load_e4()
    t = fig_results(rows, e3recs, e4recs)
    open(os.path.join("results", "fig_results.tex"), "w", encoding="utf-8", newline="\n").write(t + "\n")
    print(t)
    p = fig_pareto(e3recs, e4recs)
    open(os.path.join("results", "fig_pareto.tex"), "w", encoding="utf-8", newline="\n").write(p + "\n")
