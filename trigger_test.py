r"""trigger_test.py: mechanics and a first timing of FD enforcement by triggers on the server's MySQL.

Copies freeman.abalone (iConf's table: VARCHAR columns `0`..`8` and an id) into bl.t_abalone, enforces the
first five non-key minimal FDs of abalone by triggers (with an index per left-hand side) and the minimal keys by
UNIQUE indexes, checks that a violating insert is rejected and a consistent one accepted, and times the
insertion of 10,000 synthetic records with and without the triggers.

usage: python3 trigger_test.py [n_fds=5] [rows=10000]
"""
import sys, time, json, random, os
import pymysql
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdlib import *
from triggers import *

SOCK = "/data/zzha969/mysql/mysql.sock"

def connect(db="bl"):
    return pymysql.connect(unix_socket=SOCK, user="root", database=db, autocommit=False, local_infile=True)

def main():
    n_fds = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    rows = int(sys.argv[2]) if len(sys.argv) > 2 else 10000
    n, F, _ = load_any(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "fds", "complete", "abalone.json"))
    Da = atomic_cover(F)
    R = (1 << n) - 1
    keys = minimal_keys(Da, R)
    nonkey = [(X, A) for (X, A) in Da.fds if not any(K & ~X == 0 for K in keys)]
    print("abalone: %d minimal FDs, %d keys, %d non-key FDs" % (len(Da), len(keys), len(nonkey)))
    cols = [str(i) for i in range(n)]
    fds = [([cols[i] for i in bits(X)], cols[A]) for (X, A) in nonkey[:n_fds]]
    keys_named = [[cols[i] for i in bits(K)] for K in keys]
    types = {c: "varchar(30)" for c in cols}
    con = connect()
    cur = con.cursor()
    cur.execute("DROP TABLE IF EXISTS t_abalone")
    cur.execute("CREATE TABLE t_abalone LIKE freeman.abalone")
    cur.execute("INSERT INTO t_abalone SELECT * FROM freeman.abalone")
    con.commit()
    cur.execute("SELECT COUNT(*) FROM t_abalone")
    print("rows:", cur.fetchone()[0])
    # keys and FD triggers
    for s in unique_statements("t_abalone", keys_named, types):
        cur.execute(s)
    for s in index_statements("t_abalone", fds, types):
        cur.execute(s)
    for s in trigger_statements("t_abalone", fds, nullsafe=True, id_col="id"):
        cur.execute(s)
    con.commit()
    print("enforced %d keys by UNIQUE and %d FDs by triggers:" % (len(keys_named), len(fds)))
    for X, A in fds:
        print("   ", ",".join(X), "->", A)
    # a violating insert: copy a stored tuple and change the right-hand side of the first FD
    X, A = fds[0]
    cur.execute("SELECT %s FROM t_abalone LIMIT 1" % ", ".join(q(c) for c in cols))
    t = list(cur.fetchone())
    t[int(A)] = (t[int(A)] or "") + "x"
    for c in cols:
        if c not in X and c != A:
            t[int(c)] = "fresh%s" % c   # keep the keys new
    try:
        cur.execute("INSERT INTO t_abalone (%s) VALUES (%s)" % (", ".join(q(c) for c in cols), ", ".join(["%s"] * n)), t)
        print("VIOLATION NOT DETECTED")
    except pymysql.err.OperationalError as e:
        print("violating insert rejected:", e.args[1])
    con.rollback()
    # a consistent insert: fresh values everywhere
    t = ["new%d_%s" % (0, c) for c in cols]
    cur.execute("INSERT INTO t_abalone (%s) VALUES (%s)" % (", ".join(q(c) for c in cols), ", ".join(["%s"] * n)), t)
    con.commit()
    print("consistent insert accepted")
    # timing: rows synthetic records, one INSERT per record, one transaction
    def timed_insert(label, tag):
        sql = "INSERT INTO t_abalone (%s) VALUES (%s)" % (", ".join(q(c) for c in cols), ", ".join(["%s"] * n))
        data = [["%s%d_%s" % (tag, r, c) for c in cols] for r in range(rows)]
        t0 = time.time()
        for row in data:
            cur.execute(sql, row)
        con.commit()
        dt = time.time() - t0
        print("%-32s %6d inserts in %.2fs (%.3f ms each)" % (label, rows, dt, 1000 * dt / rows))
    timed_insert("keys + %d FD triggers" % len(fds), "a")
    for s in drop_trigger_statements("t_abalone"):
        cur.execute(s)
    con.commit()
    timed_insert("keys only (triggers dropped)", "b")
    cur.execute("DROP TABLE t_abalone")
    con.commit()
    con.close()

if __name__ == "__main__":
    main()
