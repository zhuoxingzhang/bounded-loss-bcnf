r"""fk_check.py: the lookup-table mechanism of e3pg.py (modes orig-f, 3nf-f, 3nfc-f) rejects an insertion that violates
the FD cage -> animal, as the exclusion constraint does, on the official PostgreSQL build (pgdb.py).

The lookup table l over (cage, animal) has UNIQUE (cage) and UNIQUE (cage, animal); the table s over (cage, animal,
keeper) has FOREIGN KEY (cage, animal) REFERENCES l (cage, animal). A record is inserted into l first with
ON CONFLICT DO NOTHING and then into s, as e3pg.py does. (1, zebra, Ann) succeeds. For (1, lion, Bob), the key of l
admits no second animal for cage 1, so the insertion into l is skipped, and the foreign key then rejects the
insertion into s. Then two concurrent transactions insert (2, zebra, Ann) and (2, lion, Bob) under READ COMMITTED,
as in concurrency_check.py: the second insertion into l waits for the first transaction and is then skipped, and
its insertion into s fails, so cage 2 holds one animal at the end.

usage: python3 fk_check.py          (its output is results/fk_check.log)
"""
import sys, os, threading, time
import psycopg2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pgdb import connect

def setup(cur):
    cur.execute("DROP TABLE IF EXISTS w.fk_check_s, w.fk_check_l")
    cur.execute("CREATE TABLE w.fk_check_l (cage text NOT NULL, animal text NOT NULL, UNIQUE (cage), UNIQUE (cage, animal))")
    cur.execute("CREATE TABLE w.fk_check_s (cage text NOT NULL, animal text NOT NULL, keeper text NOT NULL, "
                "FOREIGN KEY (cage, animal) REFERENCES w.fk_check_l (cage, animal))")

def insert(cur, cage, animal, keeper):
    cur.execute("INSERT INTO w.fk_check_l (cage, animal) VALUES (%s, %s) ON CONFLICT DO NOTHING", (cage, animal))
    cur.execute("INSERT INTO w.fk_check_s (cage, animal, keeper) VALUES (%s, %s, %s)", (cage, animal, keeper))

def sequential():
    con = connect()
    cur = con.cursor()
    setup(cur)
    con.commit()
    insert(cur, "1", "zebra", "Ann")
    con.commit()
    print("(1, zebra, Ann): inserted")
    try:
        insert(cur, "1", "lion", "Bob")
        con.commit()
        print("(1, lion, Bob): inserted, the FD is violated")
    except psycopg2.Error as e:
        con.rollback()
        print("(1, lion, Bob): rejected:", str(e).strip().splitlines()[0])
    cur.execute("SELECT count(DISTINCT animal) FROM w.fk_check_s WHERE cage = '1'")
    print("animals in cage 1:", cur.fetchone()[0])
    con.close()

def concurrent():
    results = {}
    def run(name, cage, animal, keeper, hold):
        con = connect()
        cur = con.cursor()
        t0 = time.time()
        try:
            insert(cur, cage, animal, keeper)
            if hold:
                time.sleep(2)
            con.commit()
            results[name] = "committed after %.1f s" % (time.time() - t0)
        except psycopg2.Error as e:
            con.rollback()
            results[name] = "failed after %.1f s: %s" % (time.time() - t0, str(e).strip().splitlines()[0])
        con.close()
    a = threading.Thread(target=run, args=("A (2, zebra, Ann)", "2", "zebra", "Ann", True))
    b = threading.Thread(target=run, args=("B (2, lion, Bob)", "2", "lion", "Bob", False))
    a.start()
    time.sleep(0.5)
    b.start()
    a.join()
    b.join()
    for k in sorted(results):
        print(k + ":", results[k])
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT count(DISTINCT animal) FROM w.fk_check_s WHERE cage = '2'")
    print("animals in cage 2:", cur.fetchone()[0])
    cur.execute("DROP TABLE IF EXISTS w.fk_check_s, w.fk_check_l")
    con.commit()
    con.close()

if __name__ == "__main__":
    con = connect()
    cur = con.cursor()
    cur.execute("SELECT version()")
    print(cur.fetchone()[0])
    con.close()
    print("-- sequential")
    sequential()
    print("-- concurrent, READ COMMITTED")
    concurrent()
