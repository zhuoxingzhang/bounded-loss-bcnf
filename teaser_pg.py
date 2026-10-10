r"""teaser_pg.py: update overheads of the designs of the running example in PostgreSQL (the teaser of the paper;
runs on the server against the official build, pgdb.py).

The schema is R = {C, S, T, Z} with Sigma = {C -> ST, ST -> Z, Z -> T}, and the synthetic address book of
teaser.py (World): `base` customers, then `size` new customers inserted (projected onto the schemata,
INSERT ... ON CONFLICT DO NOTHING in batches of 1,000 rows, one transaction, the commit included), reps times
per size. Half of the new customers move to an existing address, the other half to a new street of an existing
town with a new zip code, so that every FD remains satisfied. Non-key FDs are enforced by exclusion constraints
(btree_gist) or by a BEFORE INSERT trigger that probes one stored tuple through an index on the left-hand side,
as in e3pg.py (the session disables sequential and bitmap scans, so that the cached plans use the index).

  D1+triggers  CSTZ with key C, ST -> Z and Z -> T by triggers
  D1+exclude   CSTZ with key C, ST -> Z and Z -> T by exclusion constraints
  3NF+trigger  {STZ (keys ST, SZ), CST (key C)} with Z -> T by a trigger
  3NF+exclude  {STZ (keys ST, SZ), CST (key C)} with Z -> T by an exclusion constraint
  D4+FK        {ZT (key Z, UNIQUE ZT), STZ (keys ST, SZ, FOREIGN KEY ZT), CST (key C)}: Z -> T through a lookup table
  D1           CSTZ with key C only (vendor guidance, loss 2)
  D2           ZT (Z), CSZ (C): classical BCNF decomposition (loss 1)
  D4           STZ (ST, SZ), CST (C): the BCNF design with loss 1

usage: python3 teaser_pg.py [--base 100000] [--sizes 10000,20000,30000] [--reps 5] [--designs D1,D2,...]
       results/teaser_pg.jsonl
"""
import sys, os, json, time, random
import psycopg2.extras
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pgdb import connect, qi
from teaser import World

HERE = os.path.dirname(os.path.abspath(__file__))
COLS = ["C", "S", "T", "Z"]
# name: list of (table, attrs, keys, FDs, enforcement of the FDs, foreign keys (attrs, table))
DESIGNS = {
    "D1+triggers": [("t_cstz", "CSTZ", ["C"], [("ST", "Z"), ("Z", "T")], "t", [])],
    "D1+exclude": [("t_cstz", "CSTZ", ["C"], [("ST", "Z"), ("Z", "T")], "x", [])],
    "3NF+trigger": [("t_stz", "STZ", ["ST", "SZ"], [("Z", "T")], "t", []), ("t_cst", "CST", ["C"], [], None, [])],
    "3NF+exclude": [("t_stz", "STZ", ["ST", "SZ"], [("Z", "T")], "x", []), ("t_cst", "CST", ["C"], [], None, [])],
    "D4+FK": [("t_zt", "ZT", ["Z", "ZT"], [], None, []), ("t_stz", "STZ", ["ST", "SZ"], [], None, [("ZT", "t_zt")]),
              ("t_cst", "CST", ["C"], [], None, [])],
    "D1": [("t_cstz", "CSTZ", ["C"], [], None, [])],
    "D2": [("t_zt", "ZT", ["Z"], [], None, []), ("t_csz", "CSZ", ["C"], [], None, [])],
    "D4": [("t_stz", "STZ", ["ST", "SZ"], [], None, []), ("t_cst", "CST", ["C"], [], None, [])],
}

def build(cur, table, attrs, keys, fds, how, fks):
    t = "w.%s" % qi("teaser_" + table)
    cur.execute("DROP TABLE IF EXISTS %s CASCADE" % t)
    cur.execute("CREATE TABLE %s (%s)" % (t, ", ".join("%s text NOT NULL" % a for a in attrs)))
    for j, K in enumerate(keys):
        cur.execute("ALTER TABLE %s ADD CONSTRAINT %s UNIQUE (%s)" % (t, qi("teaser_%s_k%d" % (table, j)), ", ".join(K)))
    for j, (X, A) in enumerate(fks):
        cur.execute("ALTER TABLE %s ADD CONSTRAINT %s FOREIGN KEY (%s) REFERENCES w.%s (%s)" % (
            t, qi("teaser_%s_f%d" % (table, j)), ", ".join(X), qi("teaser_" + A), ", ".join(X)))
    if how == "x":
        for j, (X, A) in enumerate(fds):
            cur.execute("ALTER TABLE %s ADD CONSTRAINT %s EXCLUDE USING gist (%s)" % (
                t, qi("teaser_%s_x%d" % (table, j)), ", ".join(["%s WITH =" % x for x in X] + ["%s WITH <>" % A])))
    elif how == "t" and fds:
        for j, (X, A) in enumerate(fds):
            if set(X) not in [set(K) for K in keys]:
                cur.execute("CREATE INDEX %s ON %s (%s)" % (qi("teaser_%s_i%d" % (table, j)), t, ", ".join(X)))
        body = "\n".join("  SELECT s.%s INTO v FROM %s s WHERE %s LIMIT 1;\n  IF FOUND AND v <> NEW.%s THEN RAISE EXCEPTION 'FD violated'; END IF;"
                         % (A, t, " AND ".join("s.%s = NEW.%s" % (x, x) for x in X), A) for X, A in fds)
        fn = "w.%s" % qi("teaser_%s_fd" % table)
        cur.execute("CREATE OR REPLACE FUNCTION %s() RETURNS trigger LANGUAGE plpgsql AS $f$\nDECLARE v text;\nBEGIN\n%s\n  RETURN NEW;\nEND\n$f$" % (fn, body))
        cur.execute("CREATE TRIGGER %s BEFORE INSERT ON %s FOR EACH ROW EXECUTE FUNCTION %s()" % (qi("teaser_%s_trg" % table), t, fn))
    return t

def main():
    args = sys.argv[1:]
    base, sizes, reps, names = 100000, [10000, 20000, 30000], 5, [d for d in DESIGNS if "trigger" not in d]
    i = 0
    while i < len(args):
        if args[i] == "--base":
            base = int(args[i + 1]); i += 2
        elif args[i] == "--sizes":
            sizes = [int(x) for x in args[i + 1].split(",")]; i += 2
        elif args[i] == "--reps":
            reps = int(args[i + 1]); i += 2
        elif args[i] == "--designs":
            names = args[i + 1].split(","); i += 2
        else:
            i += 1
    con = connect()
    cur = con.cursor()
    cur.execute("SET enable_seqscan = off")
    cur.execute("SET enable_bitmapscan = off")
    con.commit()
    out = open(os.path.join(HERE, "results", "teaser_pg.jsonl"), "a", encoding="utf-8")
    for name in names:
        tables = DESIGNS[name]
        for size in sizes:
            for rep in range(reps):
                rng = random.Random(1000 * size + rep)
                world = World(rng)
                basedata = world.customers(base, 0)
                for table, attrs, keys, fds, how, fks in reversed(tables):
                    cur.execute("DROP TABLE IF EXISTS w.%s CASCADE" % qi("teaser_" + table))
                built = []
                for table, attrs, keys, fds, how, fks in tables:
                    t = build(cur, table, attrs, [list(K) for K in keys], [(list(X), A) for X, A in fds], how,
                              [(list(X), A) for X, A in fks])
                    idx = [COLS.index(a) for a in attrs]
                    rows = sorted(set(tuple(r[j] for j in idx) for r in basedata))
                    psycopg2.extras.execute_values(cur, "INSERT INTO %s (%s) VALUES %%s" % (t, ", ".join(attrs)), rows, page_size=10000)
                    cur.execute("ANALYZE %s" % t)
                    built.append((t, attrs))
                con.commit()
                newdata = world.customers(size, base)
                stmts = [("INSERT INTO %s (%s) VALUES %%s ON CONFLICT DO NOTHING" % (t, ", ".join(attrs)), [COLS.index(a) for a in attrs]) for t, attrs in built]
                t0 = time.time()
                inserted = 0
                for b in range(0, size, 1000):
                    batch = newdata[b:b + 1000]
                    for sql, idx in stmts:
                        psycopg2.extras.execute_values(cur, sql, [tuple(r[j] for j in idx) for r in batch], page_size=1000)
                        inserted += cur.rowcount
                con.commit()
                secs = time.time() - t0
                rec = dict(design=name, dbms="postgresql", base=base, size=size, rep=rep, seconds=round(secs, 3), inserted=inserted)
                out.write(json.dumps(rec) + "\n")
                out.flush()
                print(time.strftime("%H:%M:%S"), name, size, rep, "%.2fs" % secs, inserted, "rows", flush=True)
        for table, attrs, keys, fds, how, fks in reversed(tables):
            cur.execute("DROP TABLE IF EXISTS w.%s CASCADE" % qi("teaser_" + table))
            cur.execute("DROP FUNCTION IF EXISTS w.%s()" % qi("teaser_%s_fd" % table))
        con.commit()
    out.close()
    con.close()

if __name__ == "__main__":
    main()
