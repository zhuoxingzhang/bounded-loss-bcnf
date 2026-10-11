r"""pgload.py: copies the source tables of E3 and E4 from MySQL (database e3, loaded by e3load.py) into PostgreSQL
(schema src of the database bcnf on the official build, see pgdb.py), so that both systems hold the same data.

Every column is text, named c0 .. c(n-1) as in MySQL. The marker of a missing value is the string '?', so that
two missing values agree as under the null equality interpretation. SQL NULLs (there should be none) are copied
as NULLs and counted.

usage: python3 pgload.py [set ...]        (default: every set of e3.SETS)
"""
import sys, os, io, time
import pymysql
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e3 import SETS, SOCK
from pgdb import connect, qi

def esc(v):
    if v is None:
        return "\\N"
    return str(v).replace("\\", "\\\\").replace("\t", "\\t").replace("\n", "\\n").replace("\r", "\\r")

def load(name, chunk=100000):
    t0 = time.time()
    my = pymysql.connect(unix_socket=SOCK, user="root", database="e3", charset="utf8mb4", cursorclass=pymysql.cursors.SSCursor)
    mc = my.cursor()
    mc.execute("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='e3' AND table_name=%s", (name,))
    n = mc.fetchone()[0]
    cols = ["c%d" % i for i in range(n)]
    pg = connect()
    pc = pg.cursor()
    pc.execute("DROP TABLE IF EXISTS src.%s" % qi(name))
    pc.execute("CREATE TABLE src.%s (%s)" % (qi(name), ", ".join("%s text" % c for c in cols)))
    mc.execute("SELECT %s FROM e3.`%s`" % (", ".join("`%s`" % c for c in cols), name))
    rows = nulls = 0
    while True:
        batch = mc.fetchmany(chunk)
        if not batch:
            break
        buf = io.StringIO()
        for r in batch:
            nulls += sum(1 for v in r if v is None)
            buf.write("\t".join(esc(v) for v in r) + "\n")
        buf.seek(0)
        pc.copy_expert("COPY src.%s FROM STDIN" % qi(name), buf)
        rows += len(batch)
    pc.execute("ANALYZE src.%s" % qi(name))
    pg.commit()
    pg.close()
    my.close()
    print("%s: %d rows, %d columns, %d NULLs, %.1fs" % (name, rows, n, nulls, time.time() - t0), flush=True)

if __name__ == "__main__":
    for name in sys.argv[1:] or list(SETS):
        load(name)
