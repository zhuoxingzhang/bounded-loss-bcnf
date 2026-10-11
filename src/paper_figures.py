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
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # the repository root, which holds data/ and results/

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

def shift(key, bar=BAR, gap=GAP):
    i = [k for k, _, _ in STYLES].index(key)
    return (i - (len(STYLES) - 1) / 2.0) * (bar + gap)

def panel(title, ylabel, names, series, log, ymin, ymax=None, legend=False, hatched=None, floor=None, dotted=None, bar=BAR, gap=GAP, extra=""):
    """one ybar axis: names are the x labels, series a list of (design key, {name: value}) with value None for a
    missing value; hatched maps design keys to the names whose bar was cut by the budget, dotted those whose value is
    a placeholder estimate; on a logarithmic axis, floor is the y value at which zeros (circles) and missing values
    (crosses) are marked; bar and gap are the bar width and the gap between the bars of a group in pt; extra holds
    further axis options"""
    out = [r"\nextgroupplot[ylabel={%s}, title={%s}, title style={font=\scriptsize, yshift=-3pt}," % (ylabel, title),
           r"  symbolic x coords={%s}, xtick=data, ymin=%s%s," % (",".join("{%s}" % n for n in names), ymin, "" if ymax is None else ", ymax=%s" % ymax),
           r"  %s%s]" % ("ymode=log, log origin=infty" if log else "ymode=normal", ", " + extra if extra else "")]
    if legend:
        for key, label, style in STYLES:
            out.append(r"\addlegendimage{%s}\addlegendentry{%s}" % (style, label))
    for key, vals in series:
        sh = "bar shift=%.2fpt" % shift(key, bar, gap)
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

def fig_results(rows, e3recs, e4recs, size=10000, budget=7200, loss_panel=True, width=r"\textwidth", height=3.6, bar=BAR, gap=GAP,
                legend_cols=-1, legend_y=1.18, vsep=36, ylabel_at=None, shared_xticklabels=False):
    """the bar panels of the losses (RQ1), the insertion times (RQ3) and the integrity risks (RQ4); with
    loss_panel=False the panel of the losses is left out and the other two are lettered (a) and (b); width, height,
    bar and gap size the panels and the bars, legend_cols and legend_y lay out the legend above the first panel,
    vsep is the distance between the panels in pt, and ylabel_at fixes the y labels at that fraction of the panel
    width left of the axis, so that the labels of panels with tick labels of different widths align; with
    shared_xticklabels only the bottom panel names the data sets (the panels show the same sets in the same order)"""
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
    letters = iter("abc")
    out = [r"\begin{tikzpicture}",
           r"\begin{groupplot}[group style={group size=1 by %d, vertical sep=%dpt}, ybar, width=%s, height=%gcm," % (3 if loss_panel else 2, vsep, width, height),
           r"  /pgf/bar width=%.1fpt, enlarge x limits=0.06, ymajorgrids, tick pos=left, tick label style={font=\scriptsize}, label style={font=\scriptsize},%s" % (
               bar, "" if ylabel_at is None else " ylabel style={at={(axis description cs:%g,0.5)}, anchor=base}," % ylabel_at),
           r"  xticklabel style={font=\scriptsize}, log ticks with fixed point,",
           r"  legend style={font=\scriptsize, at={(0.5,%g)}, anchor=south, legend columns=%d, draw=none, fill=none, /tikz/every even column/.append style={column sep=6pt}}," % (legend_y, legend_cols),
           r"  legend image code/.code={\draw[#1] (0cm,-0.07cm) rectangle (0.32cm,0.07cm);}]"]
    # the upper panels drop the names of the sets when the bottom panel names the same sets (groupplots'
    # `xticklabels at=edge bottom` does not silence symbolic x coordinates)
    upper = r"xticklabel=\empty" if shared_xticklabels else ""
    if loss_panel:
        out += panel("(%s) dependency loss (RQ1)" % next(letters), "minimal FDs", names1,
                     [(k, loss[k]) for k in ("keys", "3nf", "3nfc", "bcnf", "gbcnf", "repair", "drop")], True, 1, legend=True, floor=1, bar=bar, gap=gap, extra=upper)
    out += panel("(%s) time for inserting 10,000 records (RQ3)" % next(letters), "seconds", names3,
                 [(k, time[k]) for k, _, _ in STYLES], True, 0.1, 20000, legend=not loss_panel, hatched=cut, dotted=dot, bar=bar, gap=gap, extra=upper)
    out += panel("(%s) integrity risk (RQ4)" % next(letters), "per cent", names4,
                 [(k, risk[k]) for k in ("keys", "3nf", "3nfc", "bcnf", "gbcnf", "repair", "drop")], True, 0.1, 100, floor=0.1, bar=bar, gap=gap)
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

def fig_pareto(e3recs, e4recs, size=10000, budget=7200, cols=4, sets=None, designs=None, width=4.9, height=3.6,
               skyline=True, drop_where_differs=False, labels=None):
    """small multiples, one per data set: insertion time (logarithmic) against integrity risk, with the staircase of
    the skyline (Pareto front); the legend is a named legend that the figure places above the plots. `sets` restricts
    the data sets (by label) and `designs` the designs (by index into PARETO); with drop_where_differs, the design of
    Drop is drawn only where it differs from that of Repair; `labels` overrides legend entries by index."""
    data = pareto_points(e3recs, e4recs, size, budget)
    names = [n for n in data if sets is None or n in sets]
    keep = list(designs) if designs is not None else list(range(len(PARETO)))
    labels = labels or {}
    rows = -(-(len(names) + 1) // cols)
    out = [r"\begin{tikzpicture}",
           r"\begin{groupplot}[group style={group size=%d by %d, horizontal sep=26pt, vertical sep=30pt, xlabels at=edge bottom, ylabels at=edge left}," % (cols, rows),
           r"  width=%gcm, height=%gcm, xmode=log, ymin=-6, ymax=106, ytick={0,25,50,75,100}, log ticks with fixed point," % (width, height),
           r"  xlabel={seconds for %s records}, ylabel={risk (\%%)}, tick label style={font=\tiny}, label style={font=\scriptsize}," % "{:,}".format(size),
           r"  title style={font=\scriptsize, yshift=-4pt}, every axis plot/.append style={mark size=1.8pt}, ymajorgrids, tick pos=left, enlarge x limits=0.12]"]
    for k, name in enumerate(names):
        pts = [p for p in data[name] if p[0] in keep]
        if drop_where_differs:
            rep = [p for p in pts if PARETO[p[0]][0] == "repair"]
            pts = [p for p in pts if PARETO[p[0]][0] != "drop" or not rep or abs(p[1] - rep[0][1]) > 0.05 * rep[0][1] or abs(p[2] - rep[0][2]) > 0.5]
        opts = ["title={%s}" % name]
        xs = [p[1] for p in pts]
        if xs:
            opts.append("xtick={%s}" % ",".join("%g" % t for t in log_ticks(min(xs), max(xs))))
        if k == 0:
            opts.append(r"legend to name=paretolegend, legend columns=%d, legend cell align=left, legend style={font=\scriptsize, draw=none, /tikz/every even column/.append style={column sep=8pt}}" % min(5, len(keep)))
        out.append(r"\nextgroupplot[%s]" % ", ".join(opts))
        if k == 0:
            for i in keep:
                _, _, label, style = PARETO[i]
                out.append(r"\addlegendimage{only marks, %s}\addlegendentry{%s}" % (style, labels.get(i, label)))
        front = pareto_front(pts)
        if skyline and len(front) > 1:
            out.append(r"\addplot[const plot, gray!70, forget plot] coordinates {%s};" % " ".join("(%.4g,%.4g)" % (p[1], p[2]) for p in front))
        for i, x, y, cut, estimated in pts:
            style = PARETO[i][3] + (", opacity=0.4" if estimated else "")
            out.append(r"\addplot[only marks, %s, forget plot] coordinates {(%.4g,%.4g)};" % (style, x, y))
            if cut:
                out.append(r"\node[font=\tiny, anchor=south] at (axis cs:%.4g,%.4g) {$>$};" % (x, y))
    out += [r"\end{groupplot}",
            r"\node[anchor=south] at ([yshift=14pt]group c%dr1.north east) {\ref{paretolegend}};" % (cols // 2) if cols % 2 == 0 else
            r"\node[anchor=south] at ([yshift=14pt]group c%dr1.north) {\ref{paretolegend}};" % (cols // 2 + 1),
            r"\end{tikzpicture}"]
    return "\n".join(out)

TRADEOFF = [("orig-x", None, "original, all FDs by exclusion", "black, mark=square*"),
            ("3nf-x", None, "3NF (iConf), FDs by exclusion", "red, mark=triangle*"),
            ("3nf", "3nf_loss", "3NF (iConf), keys only", "red, mark=triangle, mark options={fill=white}"),
            ("keys", "nu", "keys only", "gray, mark=*"),
            ("bcnf", "bcnf_loss", "BCNF", "orange!80!black, mark=diamond*"),
            ("repair", "repair_loss", r"\repair", "blue, mark=pentagon*"),
            ("drop", "drop_loss", r"\drop, where it differs", "green!50!black, mark=star, mark size=2.4pt")]

def decade_ticks(lo, hi, max_labels=None, enlarge=0.12):
    """(ticks, labels): the powers of ten inside the axis range, which pgfplots enlarges by `enlarge` of the
    logarithmic span of [lo, hi] on each side; every decade keeps its tick mark, and with max_labels only every
    other one keeps its label when there are more (labels None: all labelled)"""
    import math
    a, b = math.log10(lo), math.log10(hi)
    pad = enlarge * max(b - a, 1e-9)
    ticks = [10 ** e for e in range(math.ceil(a - pad), math.floor(b + pad) + 1)] or [10 ** math.floor(a)]
    labels = None
    if max_labels and len(ticks) > max_labels:
        labels = ["{:,}".format(t) if i % 2 == 0 else "" for i, t in enumerate(ticks)]
    return ticks, labels

def fig_tradeoff(rows, e3recs, size=10000, budget=7200, cols=4, sets=None, width=4.6, height=3.3, floor=0.5,
                 mark_size=1.8, legend_cols=5, labels=None, hsep=26, vsep=30, one_ylabel=True, one_xlabel=False,
                 legend_font=r"\scriptsize", legend_sep=8, label_font=r"\scriptsize", legend_yshift=14, decades=False,
                 max_xlabels=None, share_rows=False, scale_only_axis=False, ylabel_at=None, xmax=None):
    """small multiples, one per data set with positive loss (or the labels in `sets`, in that order): the time for
    inserting `size` records (logarithmic) against the dependency loss (logarithmic, with loss zero at the floor);
    the design of Drop appears only where it differs from that of Repair, an estimated time is drawn pale, and a
    time the budget cancelled sits at the budget with a > sign; `labels` overrides legend entries by index;
    one_ylabel puts the y label on the middle row only, one_xlabel the x label under the middle column only, and
    xmax maps set labels to an upper x limit that extends the axis (and its decade ticks) beyond the data"""
    import e3
    byname = {r["name"]: r for r in rows}
    labels = labels or {}
    data = {}
    for name, recs in e3recs.items():
        r = byname.get(e3.SETS[name])
        label = e3_label(name)
        if r is None or (sets is not None and label not in sets) or (sets is None and not (r.get("repair_loss") or 0) > 0):
            continue
        pts = []
        for i, (mode, field, _, _) in enumerate(TRADEOFF):
            mean, sd, n, cut = e3_mean(recs, mode, size)
            if mean is None and not cut:
                continue
            loss = 0 if field is None else r.get(field)
            if loss is None:
                continue
            pts.append((i, budget if mean is None else mean, max(loss, floor), mean is None, e3_estimated(recs, mode, size)))
        rep = [p for p in pts if TRADEOFF[p[0]][0] == "repair"]
        pts = [p for p in pts if TRADEOFF[p[0]][0] != "drop" or not rep or p[2] != rep[0][2] or abs(p[1] - rep[0][1]) > 0.05 * rep[0][1]]
        data[label] = pts
    names = [s for s in sets if s in data] if sets else list(data)
    rows_ = -(-(len(names) + 1) // cols) if len(names) % cols else len(names) // cols
    # with share_rows, the panels of a row share the y range (the decade above the largest loss of the row) and only
    # the first column carries y tick labels
    import math
    rowmax = [10 ** math.ceil(math.log10(max(p[2] for n in names[r * cols:(r + 1) * cols] for p in data[n]))) for r in range(rows_)] if share_rows else []
    out = [r"\begin{tikzpicture}",
           r"\begin{groupplot}[group style={group size=%d by %d, horizontal sep=%dpt, vertical sep=%dpt, xlabels at=edge bottom, ylabels at=edge left%s},"
           % (cols, rows_, hsep, vsep, ", yticklabels at=edge left" if share_rows else ""),
           r"  %swidth=%gcm, height=%gcm, xmode=log, ymode=log, log ticks with fixed point, ymin=%g, ytick={1,10,100,1000,10000},"
           % ("scale only axis, " if scale_only_axis else "", width, height, floor * 0.6),
           r"  extra y ticks={%g}, extra y tick style={grid=none}," % floor,
           r"  %stick label style={font=\tiny}, label style={font=%s}," % ("" if one_xlabel else "xlabel={seconds for %s records}, " % "{:,}".format(size), label_font),
           r"  %s%stitle style={font=\scriptsize, yshift=-4pt}, every axis plot/.append style={mark size=%gpt}, ymajorgrids, tick pos=left, enlarge x limits=0.12, enlarge y limits={upper, value=0.15}]"
           % ("" if one_ylabel else "ylabel={dependency loss}, ",
              # a y label at a fixed distance from the axis, so that the labels of rows with tick labels of different widths align
              "" if ylabel_at is None else "ylabel style={at={(axis description cs:%g,0.5)}, anchor=base}, " % ylabel_at, mark_size)]
    for k, name in enumerate(names):
        pts = data[name]
        opts = ["title={%s}" % name]
        if one_ylabel and k == cols * (rows_ // 2):
            # one y label, on the first panel of the middle row
            opts.append("ylabel={dependency loss}")
        if one_xlabel and k == cols * (rows_ - 1) + cols // 2:
            # one x label, under the middle panel of the bottom row
            opts.append("xlabel={seconds for %s records}" % "{:,}".format(size))
        if share_rows:
            opts.append("ymax=%g" % rowmax[k // cols])
        # the label 0 of the floor tick, on every panel or only in the first column when the rows share their y axis
        opts.append("extra y tick labels={%s}" % ("0" if not share_rows or k % cols == 0 else ""))
        xs = [p[1] for p in pts]
        if xs and (xmax or {}).get(name):
            opts.append("xmax=%g" % xmax[name])
            xs.append(xmax[name])
        if xs:
            ticks, labs = decade_ticks(min(xs), max(xs), max_xlabels) if decades else (log_ticks(min(xs), max(xs)), None)
            opts.append("xtick={%s}" % ",".join("%g" % t for t in ticks))
            if labs:
                opts.append("xticklabels={%s}" % ",".join("{%s}" % l for l in labs))
        if k == 0:
            opts.append(r"legend to name=tradeofflegend, legend columns=%d, legend cell align=left, legend style={font=%s, draw=none, /tikz/every even column/.append style={column sep=%dpt}}" % (legend_cols, legend_font, legend_sep))
        out.append(r"\nextgroupplot[%s]" % ", ".join(opts))
        if k == 0:
            for i, (_, _, label, style) in enumerate(TRADEOFF):
                out.append(r"\addlegendimage{only marks, %s}\addlegendentry{%s}" % (style.replace("mark size=2.4pt", "mark size=%gpt" % (mark_size * 1.3)), labels.get(i, label)))
        for i, x, y, cut, estimated in pts:
            style = TRADEOFF[i][3].replace("mark size=2.4pt", "mark size=%gpt" % (mark_size * 1.3)) + (", opacity=0.4" if estimated else "")
            out.append(r"\addplot[only marks, %s, forget plot] coordinates {(%.4g,%.4g)};" % (style, x, y))
            if cut:
                out.append(r"\node[font=\tiny, anchor=south] at (axis cs:%.4g,%.4g) {$>$};" % (x, y))
    out += [r"\end{groupplot}",
            r"\node[anchor=south] at ([yshift=%dpt]group c%dr1.north east) {\ref{tradeofflegend}};" % (legend_yshift, cols // 2) if cols % 2 == 0 else
            r"\node[anchor=south] at ([yshift=%dpt]group c%dr1.north) {\ref{tradeofflegend}};" % (legend_yshift, cols // 2 + 1),
            r"\end{tikzpicture}"]
    return "\n".join(out)

if __name__ == "__main__":
    rows = paper_rows()
    e3recs, e4recs = load_e3(), load_e4()
    # the single-column variant of the paper: time and risk on the nine E3/E4 sets, legend in two rows
    t = fig_results(rows, e3recs, e4recs, loss_panel=False, width=r"\columnwidth", height=3.3, bar=2.0, gap=0.25, legend_cols=4, legend_y=1.2,
                    vsep=18, ylabel_at=-0.1, shared_xticklabels=True)
    open(os.path.join(ROOT, "results", "fig_results.tex"), "w", encoding="utf-8", newline="\n").write(t + "\n")
    print(t)
    # the single-column variant of the paper: the six largest sets with positive loss in three columns and two rows,
    # a compact legend in two rows above, one x label and a y label per row
    # (plot boxes of 2.1 by 1.6 cm: three boxes, the tick labels of the first column and the two gaps fill the column)
    t = fig_tradeoff(rows, e3recs, cols=3, sets=["abalone", "bridges", "echo", "ncvoter", "weather", "hepatitis"], width=2.1, height=1.6,
                     mark_size=2.2, legend_cols=4, hsep=7, vsep=20, one_ylabel=False, one_xlabel=True, legend_font=r"\tiny", legend_sep=3,
                     label_font=r"\scriptsize", legend_yshift=8, decades=True, max_xlabels=None, share_rows=True, scale_only_axis=True, ylabel_at=-0.34,
                     labels={0: "original, exclusion", 1: "3NF, exclusion", 2: "3NF, keys only", 6: r"\drop, where it differs"},
                     xmax={"bridges": 100, "echo": 100})
    open(os.path.join(ROOT, "results", "fig_tradeoff.tex"), "w", encoding="utf-8", newline="\n").write(t + "\n")
    p = fig_pareto(e3recs, e4recs)
    open(os.path.join(ROOT, "results", "fig_pareto.tex"), "w", encoding="utf-8", newline="\n").write(p + "\n")
