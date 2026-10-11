r"""dbload.py: load the CSV data sets into MySQL (experiments E3 and E4).

For every data set a table with the column names of the FD files (c0, c1, ... unless the CSV has a header) is
created in database `bl` with inferred column types (INT, DECIMAL, DOUBLE or VARCHAR of the maximal length),
'?' and empty fields become NULL on the incomplete data sets, and the rows are loaded with LOAD DATA LOCAL INFILE.

usage: python dbload.py <mysql-client> <defaults-file> <csv-dir> [name ...]
"""
import sys, os, csv, subprocess, tempfile

SETS = {
    # name: (file, delimiter, header, incomplete)
    "abalone": ("abalone.csv", ",", False, False),
    "adult": ("adult.csv", ";", False, False),
    "breast": ("breast-cancer-wisconsin.csv", ",", False, True),
    "bridges": ("bridges.csv", ",", False, True),
    "echo": ("echocardiogram.csv", ",", False, True),
    "hepatitis": ("hepatitis.csv", ",", False, True),
    "letter": ("letter.csv", ",", False, False),
    "ncvoter": ("ncvoter_1001r_19c.csv", ",", True, True),
    "fdred": ("fd-reduced-30.csv", ",", True, False),
}
NULLS = {"?", ""}

def infer(values):
    """INT, DECIMAL(p,s), DOUBLE or VARCHAR(n) for a column"""
    is_int = is_dec = True
    maxlen = 1
    ip = fp = 0
    for v in values:
        if v is None:
            continue
        maxlen = max(maxlen, len(v))
        if is_int:
            try:
                int(v)
                if len(v.lstrip("-")) > 18:
                    is_int = False
            except ValueError:
                is_int = False
        if is_dec:
            t = v.lstrip("-")
            if t.replace(".", "", 1).isdigit() and t.count(".") <= 1 and len(t) <= 30:
                a, _, b = t.partition(".")
                ip = max(ip, len(a))
                fp = max(fp, len(b))
            else:
                is_dec = False
    if is_int:
        return "BIGINT" if maxlen > 9 else "INT"
    if is_dec and ip + fp <= 30:
        return "DECIMAL(%d,%d)" % (ip + fp, fp)
    return "VARCHAR(%d)" % max(8, min(4000, maxlen + maxlen // 4))

def load(name, client, defaults, csvdir):
    fname, delim, header, incomplete = SETS[name]
    path = os.path.join(csvdir, fname)
    with open(path, encoding="utf-8", errors="replace", newline="") as f:
        rows = list(csv.reader(f, delimiter=delim))
    cols = None
    if header:
        cols = [c.strip().strip('"') or ("c%d" % i) for i, c in enumerate(rows[0])]
        rows = rows[1:]
    n = max(len(r) for r in rows)
    rows = [r + [""] * (n - len(r)) for r in rows if any(x.strip() for x in r)]
    if cols is None:
        cols = ["c%d" % i for i in range(n)]
    cols = ["".join(ch if ch.isalnum() or ch == "_" else "_" for ch in c) for c in cols]
    seen = {}
    for i, c in enumerate(cols):
        if c in seen or c[:1].isdigit():
            c = "c%d_%s" % (i, c)
        seen[c] = 1
        cols[i] = c
    data = []
    for r in rows:
        data.append([None if (incomplete and v.strip() in NULLS) else v.strip() for v in r])
    types = [infer([r[i] for r in data]) for i in range(n)]
    with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False, encoding="utf-8", newline="\n") as out:
        for r in data:
            out.write("\t".join("\\N" if v is None else v.replace("\\", "\\\\").replace("\t", " ") for v in r) + "\n")
        tsv = out.name
    ddl = "CREATE DATABASE IF NOT EXISTS bl;\nUSE bl;\nDROP TABLE IF EXISTS `%s`;\nCREATE TABLE `%s` (%s) ENGINE=InnoDB;\n" % (
        name, name, ", ".join("`%s` %s NULL" % (c, t) for c, t in zip(cols, types)))
    ldl = "LOAD DATA LOCAL INFILE '%s' INTO TABLE bl.`%s` FIELDS TERMINATED BY '\\t' LINES TERMINATED BY '\\n';\n" % (tsv.replace("\\", "/"), name)
    sql = ddl + ldl + "SELECT '%s' AS tbl, COUNT(*) AS rows_loaded FROM bl.`%s`;\n" % (name, name)
    r = subprocess.run([client, "--defaults-file=" + defaults, "--local-infile=1"], input=sql, capture_output=True, text=True)
    os.unlink(tsv)
    print(name, "columns:", ", ".join("%s %s" % (c, t) for c, t in zip(cols, types)))
    print(r.stdout.strip(), r.stderr.strip())

if __name__ == "__main__":
    client, defaults, csvdir = sys.argv[1:4]
    names = sys.argv[4:] or list(SETS)
    for name in names:
        load(name, client, defaults, csvdir)
