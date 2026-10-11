r"""concurrency_check.py: two concurrent transactions insert tuples that violate the FD cage -> animal, once under an
exclusion constraint and once under a BEFORE INSERT trigger that looks up a stored tuple with the same cage
(e3pg.py), on the official PostgreSQL build (pgdb.py), under READ COMMITTED, REPEATABLE READ and SERIALIZABLE.

Transaction A inserts (1, zebra) and keeps its transaction open for two seconds; meanwhile transaction B inserts
(1, lion) and commits. The script reports whether B waited for A, whether one of them failed, and how many animals
cage 1 holds at the end (2 means that the FD is violated in the database).

usage: python3 concurrency_check.py
"""
import sys, os, threading, time
import psycopg2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pgdb import connect

LEVELS = ["READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"]

def setup(how):
    con = connect(autocommit=True)
    cur = con.cursor()
    cur.execute("DROP TABLE IF EXISTS w.zoo CASCADE")
    cur.execute("CREATE TABLE w.zoo (cage text NOT NULL, animal text NOT NULL)")
    if how == "exclude":
        cur.execute("ALTER TABLE w.zoo ADD EXCLUDE USING gist (cage WITH =, animal WITH <>)")
    else:
        cur.execute("CREATE INDEX ON w.zoo (cage)")
        cur.execute("""CREATE OR REPLACE FUNCTION w.zoo_fd() RETURNS trigger LANGUAGE plpgsql AS $f$
DECLARE v text;
BEGIN
  SELECT s.animal INTO v FROM w.zoo s WHERE s.cage = NEW.cage LIMIT 1;
  IF FOUND AND v <> NEW.animal THEN RAISE EXCEPTION 'FD cage -> animal violated'; END IF;
  RETURN NEW;
END
$f$""")
        cur.execute("CREATE TRIGGER zoo_fd BEFORE INSERT ON w.zoo FOR EACH ROW EXECUTE FUNCTION w.zoo_fd()")
    con.close()

def run(how, level):
    setup(how)
    a, b = connect(), connect()
    for c in (a, b):
        c.cursor().execute("SET TRANSACTION ISOLATION LEVEL " + level)
    res = {}
    a.cursor().execute("INSERT INTO w.zoo VALUES ('1', 'zebra')")
    def tb():
        t0 = time.time()
        try:
            b.cursor().execute("INSERT INTO w.zoo VALUES ('1', 'lion')")
            b.commit()
            res["b"] = "committed"
        except psycopg2.Error as e:
            b.rollback()
            res["b"] = "failed: " + e.pgerror.splitlines()[0] if e.pgerror else "failed"
        res["b_wait"] = time.time() - t0
    th = threading.Thread(target=tb)
    th.start()
    time.sleep(2)
    try:
        a.commit()
        res["a"] = "committed"
    except psycopg2.Error as e:
        a.rollback()
        res["a"] = "failed: " + (e.pgerror or "").splitlines()[0]
    th.join()
    c = connect(autocommit=True)
    cur = c.cursor()
    cur.execute("SELECT count(DISTINCT animal) FROM w.zoo WHERE cage = '1'")
    res["animals_in_cage_1"] = cur.fetchone()[0]
    cur.execute("DROP TABLE w.zoo CASCADE")
    cur.execute("DROP FUNCTION IF EXISTS w.zoo_fd()")
    for x in (a, b, c):
        x.close()
    return res

if __name__ == "__main__":
    for how in ("exclude", "trigger"):
        for level in LEVELS:
            r = run(how, level)
            print("%-8s %-16s A %-10s B %-60s B waited %.1fs, animals in cage 1: %d" % (
                how, level, r["a"], r["b"], r["b_wait"], r["animals_in_cage_1"]), flush=True)
