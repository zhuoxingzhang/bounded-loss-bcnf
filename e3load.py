r"""e3load.py: the source tables of experiments E3 and E4 in the database e3 (runs on the server).

Every data set becomes a table e3.<set> with VARCHAR columns c0, ..., c(n-1) in the column order of its FD
file, values as in the CSV (the missing-value marker '?' stays the string '?', so that equality of the strings
is the null equality interpretation under which the FDs were discovered), duplicate rows removed, and column
lengths fitted to the data (at least 12 characters, room for the synthetic values of E3). weather comes from the
iConf table freeman.`china_weather(nulleq)`, tpch_orders and tpch_part from the TPC-H tables (scale factor 1)
by casting every column to a string.

usage: python3 e3load.py [set ...]        (default: all sets)
"""
import sys, os, csv, tempfile
import pymysql
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdlib import load_metanome_txt

SOCK = "/data/zzha969/mysql/mysql.sock"
CSVDIR = "/data/zzha969/data/hpi"
FDDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "fds")
MINLEN = 12

CSV = {
    # set: (file, delimiter, header)
    "abalone": ("abalone.csv", ",", False),
    "adult": ("adult.csv", ";", False),
    "breast": ("breast-cancer-wisconsin.csv", ",", False),
    "bridges": ("bridges.csv", ",", False),
    "echo": ("echocardiogram.csv", ",", False),
    "hepatitis": ("hepatitis.csv", ",", False),
    "letter": ("letter.csv", ",", False),
    "ncvoter": ("ncvoter_1001r_19c.csv", ",", True),
    "fdred": ("fd-reduced-30.csv", ",", True),
}
ICONF = {"weather": ("freeman", "china_weather(nulleq)", 18)}
TPCH = {"tpch_orders": ("orders", "orders-fds.txt"), "tpch_part": ("part", "part-fds.txt")}

def connect():
    return pymysql.connect(unix_socket=SOCK, user="root", autocommit=True, local_infile=True, charset="utf8mb4")

def q(c):
    return "`%s`" % c

def load_csv(cur, name):
    fname, delim, header = CSV[name]
    with open(os.path.join(CSVDIR, fname), encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.reader(f, delimiter=delim))
    if header:
        rows = rows[1:]
    n = max(len(r) for r in rows)
    data = set()
    for r in rows:
        if not any(x.strip() for x in r):
            continue
        r = r + [""] * (n - len(r))
        data.add(tuple(v.strip() for v in r))
    data = sorted(data)
    lens = [max(MINLEN, max(len(r[i]) for r in data) + 2) for i in range(n)]
    cols = ["c%d" % i for i in range(n)]
    with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False, encoding="utf-8", newline="\n") as out:
        for r in data:
            out.write("\t".join(v.replace("\\", "\\\\").replace("\t", " ") for v in r) + "\n")
        tsv = out.name
    cur.execute("DROP TABLE IF EXISTS e3.%s" % q(name))
    cur.execute("CREATE TABLE e3.%s (%s) ENGINE=InnoDB" % (q(name), ", ".join("%s VARCHAR(%d) NOT NULL" % (q(c), L) for c, L in zip(cols, lens))))
    cur.execute("LOAD DATA LOCAL INFILE '%s' INTO TABLE e3.%s FIELDS TERMINATED BY '\\t' LINES TERMINATED BY '\\n'" % (tsv, q(name)))
    os.unlink(tsv)
    cur.execute("SELECT COUNT(*) FROM e3.%s" % q(name))
    print("%s: %d columns, %d distinct rows loaded (%d in the file)" % (name, n, cur.fetchone()[0], len(rows)), flush=True)

def fit_lengths(cur, name, n):
    for i in range(n):
        cur.execute("SELECT MAX(CHAR_LENGTH(%s)) FROM e3.%s" % (q("c%d" % i), q(name)))
        L = max(MINLEN, (cur.fetchone()[0] or 0) + 2)
        cur.execute("ALTER TABLE e3.%s MODIFY %s VARCHAR(%d) NOT NULL" % (q(name), q("c%d" % i), L))

def load_iconf(cur, name):
    db, table, n = ICONF[name]
    sel = ", ".join("COALESCE(%s, '?') AS %s" % (q(str(i)), q("c%d" % i)) for i in range(n))
    cur.execute("DROP TABLE IF EXISTS e3.%s" % q(name))
    cur.execute("CREATE TABLE e3.%s ENGINE=InnoDB AS SELECT DISTINCT %s FROM %s.%s" % (q(name), sel, q(db), q(table)))
    fit_lengths(cur, name, n)
    cur.execute("SELECT COUNT(*) FROM e3.%s" % q(name))
    print("%s: %d columns, %d distinct rows from %s.%s" % (name, n, cur.fetchone()[0], db, table), flush=True)

def load_tpch(cur, name):
    table, fdfile = TPCH[name]
    n, F, names = load_metanome_txt(os.path.join(FDDIR, "tpch", fdfile))
    sel = ", ".join("COALESCE(CAST(%s AS CHAR), '?') AS %s" % (q(names[i]), q("c%d" % i)) for i in range(n))
    cur.execute("DROP TABLE IF EXISTS e3.%s" % q(name))
    cur.execute("CREATE TABLE e3.%s ENGINE=InnoDB AS SELECT DISTINCT %s FROM tpch.%s" % (q(name), sel, q(table)))
    fit_lengths(cur, name, n)
    cur.execute("SELECT COUNT(*) FROM e3.%s" % q(name))
    print("%s: %d columns (%s), %d distinct rows from tpch.%s" % (name, n, ", ".join(names), cur.fetchone()[0], table), flush=True)

def main():
    names = sys.argv[1:] or list(CSV) + list(ICONF) + list(TPCH)
    con = connect()
    cur = con.cursor()
    cur.execute("CREATE DATABASE IF NOT EXISTS e3")
    cur.execute("CREATE DATABASE IF NOT EXISTS e3w")
    for name in names:
        if name in CSV:
            load_csv(cur, name)
        elif name in ICONF:
            load_iconf(cur, name)
        elif name in TPCH:
            load_tpch(cur, name)
        else:
            print("unknown set", name)
    con.close()

if __name__ == "__main__":
    main()
