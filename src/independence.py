r"""independence.py: independence (Thm. "Independence") of every design of E1 and E4, and the sources and parts
(Thm. "Decomposition by sources") of every FD set of E1.

A key design is independent iff for all distinct schemata S, T and every declared key K of T inside the closure
S+_{-T} of S under the key dependencies of the other schemata, T - K and S+_{-T} are disjoint. The closure of S under
all key dependencies records the key dependencies that fire, and S+_{-T} differs from it only for the schemata T among
them, so every schema S needs one closure plus one per such T. A failure is reported with its witness S, T, K.

A source is an attribute that is the right-hand side of no minimal FD; the parts are the connected components of the
graph on the other attributes that joins B and A whenever B is in X for a minimal FD X -> A, and R_P adds to a part P
the sources in the left-hand sides of the minimal FDs with right-hand side in P.

The designs are those of the records of experiments.py, meaningful.py, gbcnf.py, hybrid.py and weighted.py; the loss
of every design is recomputed and checked against its record.

usage: python src/independence.py [set ...]     results/independence.jsonl and results/parts.jsonl, and a summary
"""
import sys, os, json, time
from fdlib import *
import experiments as e

SETS = ["abalone", "breast(null)", "bridges(null)", "echo(null)", "adult", "letter(non-dup)", "ncvoter(null)",
        "china_weather(null)", "tpch-lineitem", "uniprot(null)", "hepatitis(null)",
        "doc-food+c1", "doc-uk", "doc-hospital", "doc-tpcds"]
E4_NAMES = {"breast(null)": "breast", "bridges(null)": "bridges", "echo(null)": "echo", "ncvoter(null)": "ncvoter",
            "china_weather(null)": "weather", "hepatitis(null)": "hepatitis", "abalone": "abalone",
            "doc-food+c1": "food", "doc-uk": "pricepaid", "doc-hospital": "hospital", "doc-tpcds": "tpcds"}


def last_record(prefix, name):
    p = os.path.join(e.ROOT, "results", "%s_%s.jsonl" % (prefix, name))
    if not os.path.isfile(p):
        return None
    rows = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    return rows[-1] if rows else None


def designs_of(name):
    """{label: (design as [(S, keys)], loss in its record)} of every design of the set"""
    out = {}
    def add(label, d, loss):
        if d:
            out[label] = ([(mask(s["attrs"]), [mask(K) for K in s["keys"]]) for s in d], loss)
    rec = last_record("e1", e.safe(name))
    ds = rec["designs"]
    add("keys", ds.get("orig"), rec["nu"])
    add("3nf", ds.get("3nf"), rec["3nf_loss"])
    add("3nfc", ds.get("3nfc"), rec.get("3nfc_loss"))
    add("bcnf", ds.get("bcnf"), rec["bcnf_loss"])
    add("repair", ds.get("repair"), rec.get("repair_loss"))
    add("drop", ds.get("drop"), rec.get("drop_loss"))
    if "gbcnf" in ds:
        add("gbcnf", ds["gbcnf"], rec.get("gbcnf_loss"))
    g = last_record("gbcnf", e.safe(name))
    if g:
        add("gbcnf", g["design"], g["gbcnf_loss"])
    h = last_record("hybrid", e.safe(name))
    if h and h.get("hybrid_design"):
        add("hybrid", h["hybrid_design"], h["hybrid_loss"])
    w = last_record("weighted", E4_NAMES.get(name, ""))
    if w:
        for m in ("repair_w", "drop_w"):
            if m in w["modes"]:
                add(m, w["modes"][m]["design"], w["modes"][m]["loss"])
    return out


def independence(n, design):
    """(True, None) or (False, (S, T, K)) by Thm. "Independence"; design is a list of (S, keys)"""
    kd, owner = [], []
    for j, (T, keys) in enumerate(design):
        for K in keys:
            for b in bits(T & ~K):
                kd.append((K, b))
                owner.append(j)
    F = FDSet(n, kd)
    assert len(F.fds) == len(kd)
    of = {}
    for i, j in enumerate(owner):
        of.setdefault(j, []).append(i)
    for i, (S, _) in enumerate(design):
        rec = []
        full = F.closure_without(S, (), rec)
        fired = set(owner[x] for x in rec)
        for j, (T, keys) in enumerate(design):
            if j == i:
                continue
            C = F.closure_without(S, of[j]) if j in fired else full
            for K in keys:
                if K & ~C == 0 and (T & ~K) & C:
                    return False, (S, T, K)
    return True, None


def fk_candidates(design):
    """the pairs of distinct schemata S, T such that S contains a declared key of T"""
    return sum(1 for i, (S, _) in enumerate(design) for j, (T, keys) in enumerate(design)
               if i != j and any(K & ~S == 0 for K in keys))


def parts(n, Da):
    """(sources, [(P, R_P, number of minimal FDs with right-hand side in P)]) by Thm. "Decomposition by sources" """
    rhs = 0
    for _, A in Da.fds:
        rhs |= 1 << A
    sources = ((1 << n) - 1) & ~rhs
    parent = {a: a for a in bits(rhs)}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for X, A in Da.fds:
        for b in bits(X & rhs):
            parent[find(b)] = find(A)
    comp = {}
    for a in bits(rhs):
        comp[find(a)] = comp.get(find(a), 0) | (1 << a)
    out = []
    for P in comp.values():
        fds = [(X, A) for X, A in Da.fds if (P >> A) & 1]
        RP = P
        for X, _ in fds:
            RP |= X & sources
        out.append((P, RP, len(fds)))
    out.sort(key=lambda t: -popcount(t[1]))
    return sources, out


def main():
    names = sys.argv[1:] or SETS
    rows, prows = [], []
    for name in names:
        t0 = time.time()
        n, F, _ = load_any(e.fd_path(name))
        Da, _ = e.sigma_a(n, F)
        src, ps = parts(n, Da)
        prows.append({"set": name, "attributes": n, "minimal_fds": len(Da), "sources": list(bits(src)),
                      "parts": [{"attrs": list(bits(P)), "R_P": popcount(RP), "minimal_fds": m} for P, RP, m in ps]})
        print("%-20s |R| %2d, %2d sources, %2d parts, largest |R_P| %2d" % (name, n, popcount(src), len(ps),
                                                                          popcount(ps[0][1]) if ps else 0), flush=True)
        for label, (d, rec_loss) in designs_of(name).items():
            t = time.time()
            E = key_dependencies(n, d)
            loss = loss_of(Da, E)
            assert rec_loss is None or loss == rec_loss, (name, label, loss, rec_loss)
            ind, wit = independence(n, d)
            r = {"set": name, "design": label, "schemata": len(d), "loss": loss, "independent": ind,
                 "fk_candidates": fk_candidates(d), "time": round(time.time() - t, 2)}
            if wit:
                S, T, K = wit
                r["witness"] = {"S": list(bits(S)), "T": list(bits(T)), "K": list(bits(K))}
            rows.append(r)
            print("   %-9s %4d schemata, loss %5d, %s, %d FK candidates (%.1fs)" % (
                label, len(d), loss, "independent" if ind else "not independent", r["fk_candidates"], r["time"]),
                flush=True)
    if not sys.argv[1:]:
        for f, rs in (("independence.jsonl", rows), ("parts.jsonl", prows)):
            with open(os.path.join(e.ROOT, "results", f), "w", encoding="utf-8") as out:
                for r in rs:
                    out.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
