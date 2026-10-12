"""fd_names.py: the minimal FDs of a data set written with the names of its columns, to select the FDs that express
rules of the domain rather than accidents of the sample.

    python src/fd_names.py <set> [...]        # E1 names, e.g. abalone breast(null) ncvoter(null); prints every FD
    python src/fd_names.py --summary <set>    # counts by right-hand side and by size of the left-hand side only

The column names of the UCI data sets (abalone, adult, breast, bridges, echo, hepatitis, letter) are those of the
UCI documentation in the order of the columns of the HPI files, which carry no header; ncvoter and uniprot carry
their names in the header of the HPI file; lineitem is the TPC-H table. The FD files index columns from 0.
"""
import os, sys
from fdlib import load_any
import experiments

NAMES = {
    "abalone": ["sex", "length", "diameter", "height", "whole_weight", "shucked_weight", "viscera_weight",
                "shell_weight", "rings"],
    "adult": ["age", "workclass", "fnlwgt", "education", "education_num", "marital_status", "occupation",
              "relationship", "race", "sex", "capital_gain", "capital_loss", "hours_per_week", "native_country",
              "income"],
    "breast(null)": ["sample_code", "clump_thickness", "cell_size_uniformity", "cell_shape_uniformity",
                     "marginal_adhesion", "epithelial_cell_size", "bare_nuclei", "bland_chromatin",
                     "normal_nucleoli", "mitoses", "class"],
    "bridges(null)": ["identif", "river", "location", "erected", "purpose", "length", "lanes", "clear_g", "t_or_d",
                      "material", "span", "rel_l", "type"],
    "echo(null)": ["survival", "still_alive", "age_at_heart_attack", "pericardial_effusion",
                   "fractional_shortening", "epss", "lvdd", "wall_motion_score", "wall_motion_index", "mult",
                   "name", "group", "alive_at_1"],
    "hepatitis(null)": ["class", "age", "sex", "steroid", "antivirals", "fatigue", "malaise", "anorexia",
                        "liver_big", "liver_firm", "spleen_palpable", "spiders", "ascites", "varices",
                        "bilirubin", "alk_phosphate", "sgot", "albumin", "protime", "histology"],
    "letter(non-dup)": ["lettr", "x_box", "y_box", "width", "high", "onpix", "x_bar", "y_bar", "x2bar", "y2bar",
                        "xybar", "x2ybr", "xy2br", "x_ege", "xegvy", "y_ege", "yegvx"],
    "ncvoter(null)": ["voter_id", "voter_reg_num", "name_prefix", "first_name", "middle_name", "last_name",
                      "name_suffix", "age", "gender", "race", "ethnic", "street_address", "city", "state",
                      "zip_code", "full_phone_num", "birth_place", "register_date", "download_month"],
    "tpch-lineitem": ["l_orderkey", "l_partkey", "l_suppkey", "l_linenumber", "l_quantity", "l_extendedprice",
                      "l_discount", "l_tax", "l_returnflag", "l_linestatus", "l_shipdate", "l_commitdate",
                      "l_receiptdate", "l_shipinstruct", "l_shipmode", "l_comment"],
}

def uniprot_names():
    f = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "uniprot_columns.txt")
    return [l.strip() for l in open(f, encoding="utf-8") if l.strip()] if os.path.exists(f) else None

def names_of(name, n):
    nm = NAMES.get(name) or (uniprot_names() if name.startswith("uniprot") else None)
    if nm is None or len(nm) != n:
        return ["c%d" % i for i in range(n)]
    return nm

def fds_of(name):
    paths = dict(experiments.SETS)
    n, F, _ = load_any(paths[name])
    nm = names_of(name, n)
    out = []
    for lhs, rhs in F.fds:
        L = [i for i in range(n) if lhs >> i & 1]
        out.append((L, rhs))
    out.sort(key=lambda t: (nm[t[1]], len(t[0]), [nm[i] for i in t[0]]))
    return n, nm, out

def main(argv):
    summary = "--summary" in argv
    for name in [a for a in argv if not a.startswith("--")]:
        n, nm, fds = fds_of(name)
        print("== %s: %d columns, %d minimal FDs" % (name, n, len(fds)))
        if summary:
            by_rhs, by_size = {}, {}
            for L, A in fds:
                by_rhs[nm[A]] = by_rhs.get(nm[A], 0) + 1
                by_size[len(L)] = by_size.get(len(L), 0) + 1
            print("  by left-hand side size:", " ".join("%d:%d" % kv for kv in sorted(by_size.items())))
            for a, c in sorted(by_rhs.items(), key=lambda kv: -kv[1]):
                print("  %5d FDs determine %s" % (c, a))
        else:
            for L, A in fds:
                print("  %s -> %s" % (", ".join(nm[i] for i in L), nm[A]))

if __name__ == "__main__":
    main(sys.argv[1:])
