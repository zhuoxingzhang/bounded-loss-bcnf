r"""trigger_test.py: mechanics and a first timing of FD enforcement by triggers on the server's MySQL.

Copies e3.abalone (VARCHAR columns c0..c8, loaded by e3load.py) into e3w.t_abalone, enforces the minimal keys
of abalone by UNIQUE indexes and the first n_fds non-key minimal FDs by triggers (with an index on every
left-hand side), checks that a violating insert is rejected and a consistent one accepted, and times the
insertion of `rows` synthetic records with the triggers, without the left-hand side indexes, and without the
triggers.

usage: python3 trigger_test.py [n_fds=5] [rows=10000]
"""
import sys, time, os
import pymysql
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdlib import *
from triggers import *

SOCK = os.environ.get("MYSQL_SOCKET", "/tmp/mysql.sock")   # the Unix socket of the MySQL server that holds the source tables

def connect():
    return pymysql.connect(unix_socket=SOCK, user="root", database="e3w", autocommit=False, charset="utf8mb4")

def main():
    n_fds = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    rows = int(sys.argv[2]) if len(sys.argv) > 2 else 10000
    n, F, _ = load_any(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "fds", "complete", "abalone.json"))
    Da = atomic_cover(F)
    R = (1 << n) - 1
    keys = minimal_keys(Da, R)
    nonkey = [(X, A) for (X, A) in Da.fds if not any(K & ~X == 0 for K in keys)]
    print("abalone: %d minimal FDs, %d keys, %d non-key FDs" % (len(Da), len(keys), len(nonkey)))
    cols = ["c%d" % i for i in range(n)]
    fds = [([cols[i] for i in bits(X)], cols[A]) for (X, A) in nonkey[:n_fds]]
    keys_named = [[cols[i] for i in bits(K)] for K in keys]
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT COLUMN_NAME, COLUMN_TYPE FROM information_schema.columns WHERE table_schema='e3' AND table_name='abalone'")
    types = dict(cur.fetchall())
    ins = "INSERT INTO e3w.t_abalone (%s) VALUES (%s)" % (", ".join(q(c) for c in cols), ", ".join(["%s"] * n))

    def setup(lhs_index, with_triggers):
        cur.execute("DROP TABLE IF EXISTS e3w.t_abalone")
        cur.execute("CREATE TABLE e3w.t_abalone ENGINE=InnoDB AS SELECT * FROM e3.abalone")
        stmts, info = enforcement_statements("t_abalone", keys_named, fds if with_triggers else [], types, lhs_index=lhs_index)
        for s in stmts:
            cur.execute(s)
        con.commit()
        return info

    info = setup(True, True)
    print("enforced:", info)
    for X, A in fds:
        print("   ", ",".join(X), "->", A)
    # a violating insert: copy a stored tuple and change the right-hand side of the first FD
    X, A = fds[0]
    cur.execute("SELECT %s FROM e3w.t_abalone LIMIT 1" % ", ".join(q(c) for c in cols))
    t = list(cur.fetchone())
    t[cols.index(A)] = t[cols.index(A)] + "x"
    for c in cols:
        if c not in X and c != A:
            t[cols.index(c)] = "~%s" % c   # keep the keys new
    try:
        cur.execute(ins, t)
        print("VIOLATION NOT DETECTED")
    except pymysql.err.OperationalError as e:
        print("violating insert rejected:", e.args[1])
    con.rollback()
    t = ["~0_%s" % c for c in cols]
    cur.execute(ins, t)
    con.commit()
    print("consistent insert accepted")

    def timed(label, tag):
        data = [["~%s%d_%s" % (tag, r, c) for c in cols] for r in range(rows)]
        t0 = time.time()
        for row in data:
            cur.execute(ins, row)
        con.commit()
        dt = time.time() - t0
        print("%-44s %6d inserts in %.2fs (%.3f ms each)" % (label, rows, dt, 1000 * dt / rows), flush=True)
    timed("keys + %d FD triggers, indexed lookups" % len(fds), "a")
    info = setup(False, True)
    timed("keys + %d FD triggers, no lhs indexes (%s)" % (len(fds), info), "b")
    info = setup(True, False)
    timed("keys only", "c")
    cur.execute("DROP TABLE e3w.t_abalone")
    con.commit()
    con.close()

if __name__ == "__main__":
    main()
