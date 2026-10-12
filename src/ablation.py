"""ablation.py: the branches of Repair (Algorithm 3) on the FD sets with positive loss, from the E1 records.

    python src/ablation.py [--tex]        # --tex also writes results/table_ablation.tex

For every FD set the record of experiments.py holds the loss of every design that Repair examines before it returns
the lightest (`repair_candidates` when the assembled set Gamma^+ is enforceable, `repair_fallback_candidates`
otherwise), labelled as in repair.py:
  assembled      the design of the assembled key dependencies Gamma (Gamma^+ enforceable)
  gamma-fix      the obstruction design of (R, Gamma^+), that is, the uncritical fixpoint of Gamma^+ (fallback)
  obstruction / sigma-fix   the obstruction design of (R, Sigma)
  gamma          the lightest enforceable subset of Gamma^+ found by the greedy (fallback)
  ascend-gamma   Ascend from the assembled design, or from the obstruction design of Gamma^+ in the fallback
  ascend-sigma   Ascend from the obstruction design of Sigma, unless the global Drop had run that ascent itself
  drop           the global Drop within the remaining budget, including its own greedy and ascents
  keys           the key-only design
"""
import json, os, sys
import experiments
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SETS = ["abalone", "breast(null)", "bridges(null)", "echo(null)", "ncvoter(null)", "china_weather(null)",
        "tpch-lineitem", "uniprot(null)", "hepatitis(null)"]
COLS = [("gamma", "$\\Gamma^+$"), ("obstruction", "$\\mathcal{O}$"), ("greedy", "greedy"),
        ("ascend-gamma", "\\ascend($\\Gamma^+$)"), ("ascend-sigma", "\\ascend($\\mathcal{O}$)"), ("drop", "\\drop")]
STAGE = {"assembled": "$\\Gamma^+$", "gamma-fix": "$\\Gamma^+$", "obstruction": "$\\mathcal{O}$", "sigma-fix": "$\\mathcal{O}$",
         "gamma": "greedy", "ascend-gamma": "\\ascend($\\Gamma^+$)", "ascend-sigma": "\\ascend($\\mathcal{O}$)",
         "drop": "\\drop", "keys": "key-only"}

def analyse(names):
    out = []
    for name in names:
        f = os.path.join(ROOT, "results", "e1_%s.jsonl" % experiments.safe(name))
        r = json.loads(open(f, encoding="utf-8").read().splitlines()[-1])
        fallback = r.get("repair_mode") == "fallback"
        cands = dict((k, v) for k, v in (r.get("repair_fallback_candidates") if fallback else r.get("repair_candidates")) or [])
        row = {"fallback": fallback, "loss": r.get("repair_loss"),
               "stage": r.get("repair_fallback_stage") if fallback else r.get("repair_stage"),
               "gamma": cands.get("gamma-fix") if fallback else cands.get("assembled"),
               "obstruction": cands.get("sigma-fix") if fallback else cands.get("obstruction"),
               "greedy": cands.get("gamma"), "ascend-gamma": cands.get("ascend-gamma"),
               "ascend-sigma": cands.get("ascend-sigma"), "drop": cands.get("drop"), "keys": cands.get("keys")}
        out.append((name, row))
    return out

def table(rows):
    from paper_tables import tex_name, num
    out = [r"\begin{tabular}{lc" + "r" * len(COLS) + "l}", r"\toprule",
           r"Data set & $\Gamma^+$ enf. & " + " & ".join(h for _, h in COLS) + r" & returned\\", r"\midrule"]
    for name, row in rows:
        cells = [num(row[k]) if row[k] is not None else "--" for k, _ in COLS]
        out.append("%s & %s & %s & %s\\\\" % (tex_name(name), "no" if row["fallback"] else "yes", " & ".join(cells), STAGE.get(row["stage"], row["stage"])))
    out += [r"\bottomrule", r"\end{tabular}"]
    return "\n".join(out)

def main(argv):
    rows = analyse([a for a in argv if a != "--tex"] or SETS)
    for name, row in rows:
        print("%-20s %-8s loss %5s  %s" % (name, "fallback" if row["fallback"] else "local", row["loss"],
              "  ".join("%s=%s" % (k, row[k]) for k, _ in COLS + [("keys", "")])), " returned:", row["stage"])
    if "--tex" in argv:
        t = table(rows)
        open(os.path.join(ROOT, "results", "table_ablation.tex"), "w", encoding="utf-8", newline="\n").write(t + "\n")
        print(t)

if __name__ == "__main__":
    main(sys.argv[1:])
