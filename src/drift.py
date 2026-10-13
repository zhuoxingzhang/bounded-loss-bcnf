r"""drift.py: the designs of weighted.py under update workloads that drift away from the one their weights came from
(runs on the server).

weighted.py weighs every minimal FD by the updates that violate it among random updates whose attribute is uniform
over the non-constant attributes, and evaluates the designs on updates of the same kind. Here the same stored
designs (Repair and Drop under unit weights and under these weights, from results/weighted_<set>.jsonl) meet updates
whose attribute follows the mixture

    p = (1 - alpha) * uniform + alpha * q,

where q is a Zipf distribution with exponent s over a random permutation of the non-constant attributes (the hot
attributes of the drifted workload). alpha = 0 is the workload of the weights; the total variation distance of p from
the uniform distribution measures the drift. As in e4.py, an update copies the value of its attribute from another
random record, it is harmful if the updated relation violates some minimal FD, and a design catches it if the
updated relation violates one of its declared key dependencies.

Every permutation k draws its updates with the seed 1000 + k for every alpha and s (common random numbers), so the
workloads of one permutation differ only in their attributes. Every update set yields one record with the harmful
updates and the missed ones per design.

usage: python3 drift.py [--perms 10] [--updates 10000] [--exponents 1,2] [--alphas 0.25,0.5,0.75,1] [set ...]
       records in results/drift_<set>.jsonl
       python3 drift.py --table
"""
import sys, os, json, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdlib import *
import experiments
from experiments import load_any
from e3 import SETS
import e4
from weighted import atomic_cover_of, fd_list

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
NAMES = ["breast", "abalone", "bridges", "echo", "ncvoter", "hepatitis", "weather"]   # the sets of weighted.py
MODES = ["repair", "repair_w", "drop", "drop_w"]


def attribute_distribution(m, alpha, s, perm):
    """the mixture of the uniform distribution and a Zipf distribution with exponent s over the m attributes in the
    order perm (perm[0] the hottest), and its total variation distance from the uniform distribution"""
    u = np.full(m, 1.0 / m)
    z = 1.0 / np.arange(1, m + 1) ** s
    q = np.empty(m)
    q[perm] = z / z.sum()
    p = (1 - alpha) * u + alpha * q
    return p, 0.5 * float(np.abs(p - u).sum())


def draw_updates(codes, nonconst, p, updates, seed):
    """as e4.draw_updates, with the attribute of an update drawn from p over the non-constant attributes"""
    rows = codes.shape[0]
    rng = np.random.default_rng(seed)
    upd_row = rng.integers(0, rows, size=updates)
    upd_attr = rng.choice(nonconst, size=updates, p=p)
    upd_val = np.empty(updates, dtype=np.int64)
    for i in range(updates):
        a = upd_attr[i]
        v = codes[rng.integers(0, rows), a]
        while v == codes[upd_row[i], a]:
            v = codes[rng.integers(0, rows), a]
        upd_val[i] = v
    n = codes.shape[1]
    mult = (rng.integers(1, 2**63 - 1, size=n, dtype=np.int64).astype(np.uint64) * np.uint64(2) + np.uint64(1))
    return upd_row, upd_attr, upd_val, mult


def run(name, perms, updates, exponents, alphas):
    t0 = time.time()
    rec = [json.loads(l) for l in open(os.path.join(ROOT, "results", "weighted_%s.jsonl" % name), encoding="utf-8") if l.strip()][-1]
    path = dict(experiments.SETS)[SETS[name]]
    n, F, _ = load_any(path)
    Da = atomic_cover_of(F, n)
    assert len(Da) == rec["minimal_fds"], (len(Da), rec["minimal_fds"])
    sigma = fd_list(Da)
    codes = e4.load_table(name)
    nonconst = [a for a in range(n) if codes[:, a].max() > 0]
    m = len(nonconst)
    kds = {mode: e4.key_dependencies_of(rec["modes"][mode]["design"]) for mode in MODES if mode in rec["modes"]}
    # the workloads: alpha = 0 once per permutation (the uniform workload with that permutation's seed), then every
    # exponent and alpha > 0
    levels = [(0.0, 0.0)] + [(s, a) for s in exponents for a in alphas]
    out_path = os.path.join(ROOT, "results", "drift_%s.jsonl" % name)
    with open(out_path, "w", encoding="utf-8") as f:
        for k in range(perms):
            perm = np.random.default_rng(100 + k).permutation(m)
            for s, alpha in levels:
                p, tv = attribute_distribution(m, alpha, s, perm)
                upd_row, upd_attr, upd_val, mult = draw_updates(codes, nonconst, p, updates, 1000 + k)
                harmful = e4.violations(codes, mult, sigma, upd_row, upd_attr, upd_val).any(axis=1)
                missed = {}
                for mode, kd in kds.items():
                    caught = e4.violations(codes, mult, kd, upd_row, upd_attr, upd_val).any(axis=1)
                    missed[mode] = int((harmful & ~caught).sum())
                r = {"set": name, "perm": k, "s": s, "alpha": alpha, "tv": round(tv, 4), "seed": 1000 + k,
                     "updates": updates, "harmful": int(harmful.sum()), "missed": missed}
                f.write(json.dumps(r) + "\n")
                f.flush()
            print("%s: permutation %d done (%.0fs)" % (name, k, time.time() - t0), flush=True)


def table():
    """per set and workload (s, alpha): the mean drift, the pooled risk of every design over the permutations, and
    in how many permutations the weighted design misses at most as many harmful updates as the unit-weight one"""
    for name in NAMES:
        p = os.path.join(ROOT, "results", "drift_%s.jsonl" % name)
        if not os.path.isfile(p):
            continue
        recs = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
        print(name)
        for s, alpha in sorted({(r["s"], r["alpha"]) for r in recs}):
            rs = [r for r in recs if r["s"] == s and r["alpha"] == alpha]
            harm = sum(r["harmful"] for r in rs)
            cells = []
            for u, w in (("repair", "repair_w"), ("drop", "drop_w")):
                if u not in rs[0]["missed"] or w not in rs[0]["missed"]:
                    continue
                ru = 100.0 * sum(r["missed"][u] for r in rs) / max(harm, 1)
                rw = 100.0 * sum(r["missed"][w] for r in rs) / max(harm, 1)
                wins = sum(r["missed"][w] <= r["missed"][u] for r in rs)
                cells.append("%s %5.1f%% -> %5.1f%% (w <= unit in %d/%d)" % (u, ru, rw, wins, len(rs)))
            print("  s=%g alpha=%.2f tv=%.2f harmful/set %6.0f | %s" % (s, alpha, np.mean([r["tv"] for r in rs]), harm / len(rs), " | ".join(cells)))


def main():
    args = sys.argv[1:]
    perms, updates, exponents, alphas, names = 10, 10000, [1.0, 2.0], [0.25, 0.5, 0.75, 1.0], []
    i = 0
    while i < len(args):
        if args[i] == "--perms":
            perms = int(args[i + 1]); i += 2
        elif args[i] == "--updates":
            updates = int(args[i + 1]); i += 2
        elif args[i] == "--exponents":
            exponents = [float(x) for x in args[i + 1].split(",")]; i += 2
        elif args[i] == "--alphas":
            alphas = [float(x) for x in args[i + 1].split(",")]; i += 2
        elif args[i] == "--table":
            table(); return
        else:
            names.append(args[i]); i += 1
    for name in names or NAMES:
        run(name, perms, updates, exponents, alphas)


if __name__ == "__main__":
    main()
