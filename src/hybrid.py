r"""hybrid.py: the algorithms Opt and Hybrid of Wei and Link (SIGMOD 2021, TODS 2025) for FDs with cardinality
constraints, ported to Python on top of fdlib as a baseline of E1.

A cardinality constraint card(X) <= l bounds the number of tuples that agree on X. The level l_X of an attribute set
X is the smallest l with Sigma |= card(X) <= l: 1 when X is a superkey, and otherwise the smallest bound among the
constraints card(Y) <= l with Y in the closure of X, since every X-group lies inside a Y-group; it is infinite when no
constraint applies. Opt (Algorithm 2 of the TODS article) synthesizes a lossless, FD-preserving decomposition from
the atomic cover: it assigns every minimal FD X -> A the largest level of the non-key FDs on its schema XA, treats
the FDs in decreasing order of these levels, removes an FD that the remaining ones imply, and otherwise adds XA as a
schema; non-maximal schemata are removed and a minimal key is added when no schema is a superkey. Hybrid (Algorithm
4) then decomposes every output schema XA along each non-key FD Y -> B on it whose level l_Y exceeds l_X, into YB and
Y(XA - B), and removes the non-maximal schemata; this trades the preservation of FDs for a lower level.

As in the experiments of the TODS article, the cardinality constraints are discovered from the data: card(X) <= l
where l is the largest number of records that agree on X, for every left-hand side X of the atomic cover
(levels_from_data). Since the FDs hold on the data, the discovered bound of X is at most the bound of every Y in
its closure, so l_X is the discovered bound of X, or 1 when X is a superkey. Without cardinality constraints
(levels_from_fds), every attribute set that is not a superkey has level infinity, and Hybrid decomposes exactly the
critical schemata that a minimal key of R generates.

The losses are those of Def. "loss" of the paper: every schema declares its minimal keys, and a minimal FD is lost
when the key dependencies do not imply it. A minimal FD that no projection implies is lost across joins in the sense
of the TODS article (Hybrid enforces these by assertions); the others are non-key FDs inside schemata.

usage: python3 hybrid.py [--no-data] [name ...]    one record per E1 set in results/hybrid_<name>.jsonl (default: all
                                                   sets; the levels come from the data where e3.SETS lists a table,
                                                   and --no-data uses the FDs alone everywhere)
       python3 hybrid.py --table                   the records next to the other designs
       python3 hybrid.py --test                    the running example of the TODS article
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdlib import *
import experiments
from experiments import SETS, safe, design_json, ASSUME_ATOMIC_ABOVE, MAX_MINIMAL

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)   # the repository root, which holds data/, results/ and iconf/
if not os.path.isdir(os.path.join(ROOT, "results")) and os.path.isdir(os.path.join(HERE, "results")):
    ROOT = HERE                # a flat copy of the scripts next to results/
INF = float("inf")

# ----------------------------------------------------------------------------- levels

def levels_from_fds(Da):
    """l_X for every left-hand side X of Da without cardinality constraints: 1 for a superkey, else infinity"""
    R = (1 << Da.n) - 1
    return {X: (1 if Da.closure(X) == R else INF) for X in set(X for X, _ in Da.fds)}

def levels_from_data(Da, codes):
    """l_X for every left-hand side X of Da from the data (codes: a NumPy array with one row per record and one
    column per attribute, as e4.load_table returns): the largest number of records that agree on X"""
    import numpy as np
    R = (1 << Da.n) - 1
    out = {}
    for X in set(X for X, _ in Da.fds):
        if Da.closure(X) == R:
            out[X] = 1
            continue
        cols = list(bits(X))
        _, counts = np.unique(codes[:, cols], axis=0, return_counts=True)
        out[X] = int(counts.max())
    return out

# ----------------------------------------------------------------------------- Opt and Hybrid

def fd_levels(Da, levels):
    """l_{X -> A} for every minimal FD: the largest level of a non-key FD on XA, or 1 when XA is in BCNF"""
    out = []
    for (X, A) in Da.fds:
        S = X | (1 << A)
        lv = [levels[Y] for (Y, B) in violators(Da, S)]
        out.append(max(lv) if lv else 1)
    return out

def opt(Da, levels):
    """Algorithm 2 (Opt): the schemata as bitmasks with their generating FDs, [(S, [(X, A), ...])]; the key schema
    added at the end, if any, has no generating FD"""
    n = Da.n
    R = (1 << n) - 1
    lv = fd_levels(Da, levels)
    order = sorted(range(len(Da.fds)), key=lambda i: -lv[i])   # decreasing level, ties in the order of Da
    disabled = set()
    schemata = {}
    gens = []
    for i in order:
        X, A = Da.fds[i]
        disabled.add(i)
        if (Da.closure_without(X, disabled) >> A) & 1:
            continue                                   # implied by the remaining FDs: removed
        disabled.discard(i)
        S = X | (1 << A)
        if S not in schemata:
            schemata[S] = []
            gens.append(S)
        schemata[S].append((X, A))
    D = [(S, schemata[S]) for S in gens]
    D = maximal(D)
    if not any(Da.closure(S) == R for S, _ in D):
        D.append((minimize_key(Da, R, R), []))
    return D

def maximal(D):
    """the schemata that no other schema of D contains (an equal schema is kept once, with the generators merged)"""
    merged = {}
    order = []
    for S, g in D:
        if S not in merged:
            merged[S] = []
            order.append(S)
        merged[S].extend(x for x in g if x not in merged[S])
    out = []
    for S in order:
        if not any(T != S and S & ~T == 0 for T in order):
            out.append((S, merged[S]))
    return out

def hybrid(Da, levels):
    """Algorithm 4 (Hybrid): the schemata of Opt, each decomposed along the non-key FDs whose level exceeds the level
    of a generating left-hand side; returns (schemata of Hybrid, schemata of Opt), both as [(S, generators)]"""
    D0 = opt(Da, levels)
    D = list(D0)
    for S, gens in D0:
        if not gens:
            continue
        lX = min(levels[X] for X, _ in gens)
        split = []
        for (Y, B) in violators(Da, S):
            if levels[Y] > lX:
                split.append((Y | (1 << B), [(Y, B)]))
                split.append((Y | (S & ~(1 << B)), []))
        if split:
            D = [(T, g) for T, g in D if T != S] + split
    return maximal(D), D0

# ----------------------------------------------------------------------------- measures

def evaluate(n, Da, schemata, levels=None):
    """the design with all minimal keys declared, its loss, the number of minimal FDs lost across joins, whether every
    schema is in BCNF, the level of the design (the largest level of a non-key FD inside a schema) and the soundness
    (chase, on small decompositions)"""
    des = keyed(Da, schemata)
    E = key_dependencies(n, des)
    proj = FDSet(n, [f for f in Da.fds if any((f[0] | (1 << f[1])) & ~S == 0 for S in schemata)])
    lost_joins = sum(1 for (X, A) in Da.fds if not proj.implies(X, A))
    level = 1
    bcnf = True
    for S in schemata:
        for (Y, B) in violators(Da, S):
            bcnf = False
            if levels is not None:
                level = max(level, levels[Y])
    try:
        sound = chase_lossless(n, schemata, E) if len(schemata) <= 40 else None
    except Exception:
        sound = None
    return des, loss_of(Da, E), lost_joins, bcnf, (None if levels is None else level), sound

def atomic(F, n):
    if len(F) > ASSUME_ATOMIC_ABOVE and all(not any(F.implies(X & ~(1 << a), A) for a in bits(X)) for (X, A) in F.fds):
        return FDSet(n, sorted(set(F.fds))), True
    return atomic_cover(F, cap=MAX_MINIMAL), False

def data_table(name):
    """the E3 table that holds the data of an E1 set, or None"""
    import e3
    for t, e1 in e3.SETS.items():
        if e1 == name:
            return t
    return None

def run(name, use_data=True):
    path = dict(SETS)[name]
    rec = {"name": name}
    t0 = time.time()
    n, F, _ = load_any(path)
    Da, assumed = atomic(F, n)
    rec.update(n=n, minimal_fds=len(Da), atomic_assumed=assumed, time_cover=round(time.time() - t0, 1))
    table = data_table(name) if use_data else None
    t1 = time.time()
    if table is not None:
        import e4
        codes = e4.load_table(table)
        rec["records"] = int(codes.shape[0])
        levels = levels_from_data(Da, codes)
        rec["levels"] = "data"
    else:
        levels = levels_from_fds(Da)
        rec["levels"] = "fds"
    rec["time_levels"] = round(time.time() - t1, 1)
    rec["level_max"] = max((l for l in levels.values() if l != INF), default=1)
    rec["level_inf"] = sum(1 for l in levels.values() if l == INF)
    t1 = time.time()
    hdec, odec = hybrid(Da, levels)
    rec["time_hybrid"] = round(time.time() - t1, 2)
    for key, dec in (("opt", odec), ("hybrid", hdec)):
        schemata = [S for S, _ in dec]
        des, loss, lost, bcnf, level, sound = evaluate(n, Da, schemata, levels)
        rec[key + "_schemata"] = len(schemata)
        rec[key + "_loss"] = loss
        rec[key + "_lost_joins"] = lost
        rec[key + "_bcnf"] = bcnf
        rec[key + "_level"] = None if level == INF else level
        rec[key + "_sound"] = sound
        rec[key + "_design"] = design_json(n, Da, des)
    if use_data and table is not None:
        # for reference, the FD-only run as well
        hdec2, _ = hybrid(Da, levels_from_fds(Da))
        _, rec["hybrid_fds_loss"], rec["hybrid_fds_lost_joins"], _, _, _ = evaluate(n, Da, [S for S, _ in hdec2])
        rec["hybrid_fds_schemata"] = len(hdec2)
    rec["time_total"] = round(time.time() - t0, 1)
    with open(os.path.join(ROOT, "results", "hybrid_%s.jsonl" % safe(name)), "w", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    print("%-22s |Da| %6d  levels from %s (max %s, %d unbounded)  Opt loss %6d (%d schemata)  Hybrid loss %6d (%d schemata, "
          "%d lost across joins%s%s)  %.1fs" % (name, len(Da), rec["levels"], rec["level_max"], rec["level_inf"],
          rec["opt_loss"], rec["opt_schemata"], rec["hybrid_loss"], rec["hybrid_schemata"], rec["hybrid_lost_joins"],
          ", BCNF" if rec["hybrid_bcnf"] else "", "" if rec["hybrid_sound"] is not False else ", UNSOUND",
          rec["time_total"]), flush=True)
    return rec

def table():
    for name, _ in SETS:
        f = os.path.join(ROOT, "results", "hybrid_%s.jsonl" % safe(name))
        if not os.path.exists(f):
            continue
        r = json.loads(open(f, encoding="utf-8").readline())
        print("%-22s %6d  levels %-4s  Opt %6d (%d)  Hybrid %6d (%d schemata, %d across joins)%s" % (
            name, r["minimal_fds"], r["levels"], r["opt_loss"], r["opt_schemata"], r["hybrid_loss"],
            r["hybrid_schemata"], r["hybrid_lost_joins"],
            "  FD-only %d (%d)" % (r["hybrid_fds_loss"], r["hybrid_fds_schemata"]) if "hybrid_fds_loss" in r else ""))

def test():
    """the running example of the TODS article: Hap over C, E, T, V with E -> C, V -> C, VT -> E, ET -> V, CT -> V
    and the cardinality constraints card(E) <= 1,000 and card(V) <= 1,000,000; Opt returns {VC, ETV, CET} and Hybrid
    {EC, VC, ETV}, which loses CT -> V across joins in terms of the given FDs, and CT -> E as well in terms of the
    atomic cover, which the loss of the paper counts"""
    names = "CETV"
    C, E, T, V = (1 << i for i in range(4))
    F = FDSet(4, [(E, 0), (V, 0), (V | T, 1), (E | T, 3), (C | T, 3)])
    Da = atomic_cover(F)
    print("atomic cover:", [fmt_fd(f, names) for f in Da.fds])
    levels = levels_from_fds(Da)
    levels[E] = 1000
    levels[V] = 1000000
    hdec, odec = hybrid(Da, levels)
    o = sorted(fmt_set(S, names) for S, _ in odec)
    h = sorted(fmt_set(S, names) for S, _ in hdec)
    print("Opt:", o, " Hybrid:", h)
    assert o == ["CET", "CV", "ETV"], o
    assert h == ["CE", "CV", "ETV"], h
    des, loss, lost, bcnf, level, sound = evaluate(4, Da, [S for S, _ in hdec], levels)
    print("Hybrid loss %d, lost across joins %d, BCNF %s, level %s, sound %s" % (loss, lost, bcnf, level, sound))
    assert (loss, lost, bcnf, level, sound) == (2, 2, True, 1, True)
    des, loss, lost, bcnf, level, sound = evaluate(4, Da, [S for S, _ in odec], levels)
    print("Opt loss %d, lost across joins %d, BCNF %s, level %s, sound %s" % (loss, lost, bcnf, level, sound))
    assert (loss, lost, bcnf, level, sound) == (1, 0, False, 1000, True)
    # without cardinality constraints Hybrid decomposes CET, which the key CT generates, along E -> C as well
    hdec, odec = hybrid(Da, levels_from_fds(Da))
    assert sorted(fmt_set(S, names) for S, _ in hdec) == ["CE", "CV", "ETV"]
    # the classical example R = ABC with AB -> C and C -> B: Opt keeps ABC, Hybrid without constraints splits it into CB and CA
    F = FDSet(3, [(0b011, 2), (0b100, 1)])
    Da = atomic_cover(F)
    hdec, odec = hybrid(Da, levels_from_fds(Da))
    assert [S for S, _ in odec] == [0b111] and sorted(S for S, _ in hdec) == [0b101, 0b110], (odec, hdec)
    print("test passed")

if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--table"]:
        table()
        sys.exit(0)
    if args[:1] == ["--test"]:
        test()
        sys.exit(0)
    use_data = True
    if args[:1] == ["--no-data"]:
        use_data = False
        args = args[1:]
    names = args or [n for n, _ in SETS]
    for name in names:
        if name not in dict(SETS):
            print("unknown set", name)
            continue
        try:
            run(name, use_data)
        except CapExceeded as e:
            print("%-22s %s" % (name, e), flush=True)
