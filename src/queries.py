r"""queries.py: the cost of reconstructing records from the tables of a design in PostgreSQL. Q_full counts the join
of all tables, and Q_point reconstructs one record from its values on a minimal key of R.

The designs are the modes keys, 3nf, 3nfc, bcnf, gbcnf, repair and drop of e3pg.py, built in schema w as there (one
table per schema with the distinct projection of src.<set> and a UNIQUE constraint per declared key). The natural
join starts from a table whose schema determines R, and every further table is, where possible, determined by its
attributes among those reached so far, preferably with a declared key among them, so that the step keeps at most one
row per row, since the data satisfies Sigma. Every step of this chain is a subquery that PostgreSQL plans on its own
(see chain): a single join of the tables, even in a fixed order (join_collapse_limit = 1), took 2.3 seconds to plan
with the 61 tables of echo and did not finish planning within four hours with the 172 tables of ncvoter. After a few dozen steps the row estimates of PostgreSQL are off by orders of
magnitude, and its choice between hash joins and nested loops flips from step to step, which made the same query up
to ten times slower; so Q_full runs with hash joins only and Q_point with nested loops only (index lookups), both with
work_mem = 64MB, under which no hash join of our data spills to disk. The record notes whether the count of the join
equals the number of records, which holds on lossless designs, and its planning time (EXPLAIN SUMMARY, once), and
both queries are prepared with one generic plan (plan_cache_mode = force_generic_plan) that a first unmeasured
execution creates; Q_point selects the record in the first step.
Q_full is then executed `reps` times, and Q_point for `lookups` records drawn at random per repetition (the seed is
the repetition), whose time is the mean latency; the repetitions run on the same tables, since queries leave the
data unchanged.

usage: python src/queries.py [--reps 5] [--lookups 1000] [--modes keys,3nf,...] [--out F] [set ...]
       results/queries_<set>.jsonl
"""
import sys, os, json, time, random, statistics
from fdlib import *
from pgdb import connect, qi
from e3 import SETS, e1_record, atomic, same_design
from e3pg import Harness, design_of
import e3pg

MODES = ["keys", "3nf", "3nfc", "bcnf", "gbcnf", "repair", "drop"]
FULL = ["SET enable_nestloop = off", "SET enable_mergejoin = off", "RESET enable_hashjoin"]    # the join methods of Q_full
POINT = ["SET enable_hashjoin = off", "SET enable_mergejoin = off", "RESET enable_nestloop"]   # and of Q_point


def join_order(Da, design):
    """(order of the schema indexes, a minimal key of R inside the first schema or None) for a chase by lookups: the
    first schema determines R under Sigma (the largest closure if none does), and every further one has a declared key
    among the attributes reached so far, or else is determined by them (the most common attributes if none is)"""
    R = (1 << Da.n) - 1
    S = [mask(s["attrs"]) for s in design]
    K = [[mask(k) for k in s["keys"]] for s in design]
    first = max(range(len(design)), key=lambda i: (Da.closure(S[i]) == R, popcount(Da.closure(S[i])), -popcount(S[i])))
    key = minimize_key(Da, S[first], R) if Da.closure(S[first]) == R else None
    order, reached = [first], S[first]
    rest = [i for i in range(len(design)) if i != first]
    while rest:
        nxt = next((i for i in rest if any(k & ~reached == 0 for k in K[i])), None)
        if nxt is None:
            nxt = next((i for i in rest if Da.closure(S[i] & reached) & S[i] == S[i]), None)
        if nxt is None:
            nxt = max(rest, key=lambda i: popcount(S[i] & reached))
        order.append(nxt)
        rest.remove(nxt)
        reached |= S[nxt]
    return order, key


BLOCK = 100   # nested steps per common table expression; the parser of PostgreSQL runs out of memory on 1,962


def chain(h, design, order, key=None):
    """(WITH clause, the natural join of the tables of h in the given order as a FROM item): step j joins step j - 1
    with the j-th table on all their common attributes, among which the index of a declared key serves the lookups
    of Q_point; with a key (attributes of the first schema), the first step keeps the row with the values $1, $2, ...
    on it. Every step is a subquery behind OFFSET 0, which PostgreSQL plans on its own and does not flatten into the
    next, and every BLOCK steps are a materialized common table expression"""
    first = order[0]
    where = "" if key is None else " WHERE " + " AND ".join("%s = $%d" % (h.cols[a], j + 1) for j, a in enumerate(key))
    sql = "SELECT %s FROM w.%s%s" % (", ".join(h.cols[a] for a in design[first]["attrs"]), qi(h.tables[first][0]), where)
    reached = mask(design[first]["attrs"])
    ctes = []
    for j, i in enumerate(order[1:], 1):
        if j % BLOCK == 0:
            ctes.append("b%d AS MATERIALIZED (%s)" % (len(ctes), sql))
            sql = "SELECT * FROM b%d" % (len(ctes) - 1)
        S = mask(design[i]["attrs"])
        sql = "SELECT s.*%s FROM (%s OFFSET 0) s JOIN w.%s t ON %s" % (
            "".join(", t.%s" % h.cols[a] for a in bits(S & ~reached)), sql, qi(h.tables[i][0]),
            " AND ".join("t.%s = s.%s" % (h.cols[a], h.cols[a]) for a in bits(S & reached)) or "true")
        reached |= S
    return ("WITH " + ", ".join(ctes)) if ctes else "", "(%s) q" % sql


def run(name, modes, reps, lookups, path=None):
    rec = e1_record(name)
    n, Da = atomic(name)
    con = connect()
    h = Harness(name, con, rec, n, Da, [1], 1, verbose=False, out=os.devnull)
    cur = h.cur
    cur.execute("RESET enable_seqscan")
    cur.execute("RESET enable_bitmapscan")
    cur.execute("SET plan_cache_mode = force_generic_plan")
    cur.execute("SET work_mem = '64MB'")
    cur.execute("SELECT count(*) FROM (SELECT DISTINCT %s FROM %s) d" % (", ".join(h.cols), h.src))
    records = cur.fetchone()[0]
    con.commit()
    done = []
    out = open(path or os.path.join(e3pg.ROOT, "results", "queries_%s.jsonl" % name), "a", encoding="utf-8")
    for mode in modes:
        design, _ = design_of(rec, mode)
        if design is None:
            continue
        dup = next((m for m, d in done if same_design(d, design)), None)
        if dup:
            out.write(json.dumps({"set": name, "mode": mode, "same_as": dup}) + "\n")
            continue
        done.append((mode, design))
        h.tables = []
        h.build(mode, design, None)
        order, key = join_order(Da, design)
        kc = None if key is None else list(bits(key))
        with_full, last = chain(h, design, order)
        cur.execute("DEALLOCATE ALL")
        for s in FULL:
            cur.execute(s)
        cur.execute("EXPLAIN (SUMMARY) %s SELECT count(*) FROM %s" % (with_full, last))
        planning = next(float(r[0].split(":")[1].split()[0]) for r in cur.fetchall() if r[0].startswith("Planning Time"))
        cur.execute("PREPARE qf AS %s SELECT count(*) FROM %s" % (with_full, last))
        if kc:
            with_point, last = chain(h, design, order, kc)
            cur.execute("PREPARE qp(%s) AS %s SELECT %s FROM %s" % (
                ", ".join(["text"] * len(kc)), with_point, ", ".join(h.cols[a] for a in range(n)), last))
            cur.execute("SELECT %s FROM %s" % (", ".join(h.cols[a] for a in kc), h.src))
            keys = cur.fetchall()
        full, point = [], []
        for rep in range(-1, reps):
            for s in FULL:
                cur.execute(s)
            t0 = time.perf_counter()
            cur.execute("EXECUTE qf")
            count = cur.fetchone()[0]
            t_full = time.perf_counter() - t0
            t_point = None
            if kc:
                rng = random.Random(rep)
                sample = [keys[rng.randrange(len(keys))] for _ in range(lookups)]
                for s in POINT:
                    cur.execute(s)
                t0 = time.perf_counter()
                for k in sample:
                    cur.execute("EXECUTE qp(%s)" % ", ".join(["%s"] * len(kc)), k)
                    cur.fetchall()
                t_point = (time.perf_counter() - t0) / lookups * 1000
            if rep >= 0:
                full.append(t_full)
                point.append(t_point)
        con.commit()
        r = {"set": name, "mode": mode, "tables": len(design), "joins": len(design) - 1, "records": records,
             "join_count": count, "lossless_join": count == records, "key": None if key is None else list(bits(key)),
             "planning_ms": planning, "q_full_s": full, "q_full_mean": statistics.mean(full), "q_full_sd": statistics.pstdev(full)}
        if kc:
            r.update({"q_point_ms": point, "q_point_mean": statistics.mean(point),
                      "q_point_sd": statistics.pstdev(point)})
        out.write(json.dumps(r) + "\n")
        out.flush()
        print("%s %-6s %4d tables | join %d of %d records | planning %.0f ms | Q_full %.3fs (sd %.3f) | Q_point %s ms" % (
            name, mode, len(design), count, records, planning, r["q_full_mean"], r["q_full_sd"],
            "%.3f (sd %.3f)" % (r["q_point_mean"], r["q_point_sd"]) if kc else "-"), flush=True)
    h.drop_tables()
    out.close()
    con.close()


def main():
    args, names = sys.argv[1:], []
    reps, lookups, modes, path = 5, 1000, MODES, None
    i = 0
    while i < len(args):
        if args[i] == "--reps":
            reps = int(args[i + 1]); i += 2
        elif args[i] == "--lookups":
            lookups = int(args[i + 1]); i += 2
        elif args[i] == "--modes":
            modes = args[i + 1].split(","); i += 2
        elif args[i] == "--out":
            path = args[i + 1]; i += 2
        else:
            names.append(args[i]); i += 1
    for name in names:
        run(name, modes, reps, lookups, path)


if __name__ == "__main__":
    main()
