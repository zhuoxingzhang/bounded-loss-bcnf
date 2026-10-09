r"""e3.py: operational overhead of the designs in MySQL (experiment E3; runs on the server).

For a data set, every design of E1 (the record results/e1_<name>.jsonl of experiments.py carries the schemata,
keys and trigger FDs of the designs) is materialised in the work database e3w: one table per schema (the
distinct projection of the source table e3.<set> of e3load.py), the minimal keys by UNIQUE indexes, the FDs the
design leaves to triggers (3NF synthesis and the original relation) by one BEFORE INSERT trigger per table with
an index on every left-hand side (triggers.py), and the keys beyond InnoDB's index budget by trigger lookups.
Then `size` synthetic records are inserted, projected onto every schema (INSERT IGNORE in batches of 1,000
rows, one transaction), and the wall-clock time is recorded; `reps` repetitions per size, the tables restored
(synthetic rows deleted) between repetitions and rebuilt for every size.

A synthetic record copies a random stored record on a closed set U of attributes (the closure of a random
subset, U != R) and carries fresh values elsewhere, so the enlarged relation satisfies every FD of Sigma: a stored
tuple that agrees with the record on X inside U agrees with it on A for every FD X -> A, every key contains a
fresh attribute, and fresh values are unique. A trigger lookup on X inside U finds the template's group and
compares right-hand sides; a lookup on X outside U finds nothing.

usage: python3 e3.py [--sizes 10000,20000,30000] [--reps 5] [--modes orig,3nf,bcnf,repair,drop,keys] [--noindex]
                     [--budget 7200] [--parallel K] [set ...]     (budget: seconds per mode and set)
       python3 e3.py --check [set ...]      verify the minimal cover and the keys on the source tables
       python3 e3.py --table                summarise results/e3_<set>.jsonl
sets: abalone adult breast bridges echo fdred hepatitis letter ncvoter weather tpch_orders tpch_part
"""
import sys, os, json, time, random, subprocess
import pymysql
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdlib import *
from triggers import enforcement_statements, q
import experiments

HERE = os.path.dirname(os.path.abspath(__file__))
SOCK = "/data/zzha969/mysql/mysql.sock"
SETS = {  # E3 set: E1 name
    "abalone": "abalone", "adult": "adult", "breast": "breast(null)", "bridges": "bridges(null)",
    "echo": "echo(null)", "fdred": "fd-red", "hepatitis": "hepatitis(null)", "letter": "letter(non-dup)",
    "ncvoter": "ncvoter(null)", "weather": "china_weather(null)", "tpch_orders": "tpch-orders", "tpch_part": "tpch-part",
}
MODES = ["orig", "3nf", "bcnf", "repair", "drop", "keys"]   # keys: the original relation with its keys only
BATCH = 1000
TEMPLATE_SEED = 42

def connect(autocommit=False):
    # the work database is the default database: the triggers refer to their tables by unqualified names
    return pymysql.connect(unix_socket=SOCK, user="root", database="e3w", autocommit=autocommit, charset="utf8mb4", local_infile=True)

def e1_record(name):
    f = os.path.join(HERE, "results", "e1_%s.jsonl" % experiments.safe(SETS[name]))
    rec = None
    for line in open(f, encoding="utf-8"):
        if line.strip():
            rec = json.loads(line)
    if rec is None or "designs" not in rec:
        raise SystemExit("no designs for %s in %s: run experiments.py --one '%s' first" % (name, f, SETS[name]))
    return rec

def atomic(name):
    """Sigma_a of the data set as E1 computes it"""
    path = dict(experiments.SETS)[SETS[name]]
    n, F, _ = load_any(path)
    if len(F) > experiments.ASSUME_ATOMIC_ABOVE:
        return n, FDSet(n, sorted(set(F.fds)))
    return n, atomic_cover(F, cap=experiments.MAX_MINIMAL)

def col_types(cur, db, table):
    cur.execute("SELECT COLUMN_NAME, COLUMN_TYPE FROM information_schema.columns WHERE table_schema=%s AND table_name=%s", (db, table))
    return {c: t for c, t in cur.fetchall()}

def same_design(d1, d2):
    key = lambda d: sorted((tuple(s["attrs"]), tuple(sorted(tuple(k) for k in s["keys"])), tuple(sorted(map(str, s.get("fds") or [])))) for s in d)
    return key(d1) == key(d2)

class Harness:
    def __init__(self, name, con, rec, n, Da, sizes, reps, lhs_index=True, budget=7200, verbose=True):
        self.name, self.con, self.rec, self.n, self.Da = name, con, rec, n, Da
        self.sizes, self.reps, self.lhs_index, self.budget, self.verbose = sizes, reps, lhs_index, budget, verbose
        self.cur = con.cursor()
        self.R = (1 << n) - 1
        self.cols = ["c%d" % i for i in range(n)]
        self.src = "e3.%s" % q(name)
        self.types = col_types(self.cur, "e3", name)
        self.cur.execute("SELECT %s FROM %s ORDER BY RAND(%d) LIMIT %d" % (", ".join(q(c) for c in self.cols), self.src, TEMPLATE_SEED, max(sizes)))
        self.templates = self.cur.fetchall()
        self.cur.execute("SELECT COUNT(*) FROM %s" % self.src)
        self.rows = self.cur.fetchone()[0]
        self.fresh = 0
        self.tables = []
        self.out = open(os.path.join(HERE, "results", "e3_%s.jsonl" % name), "a", encoding="utf-8")

    def log(self, *a):
        if self.verbose:
            print(time.strftime("%H:%M:%S"), self.name, *a, flush=True)

    def write(self, rec):
        self.out.write(json.dumps(rec) + "\n")
        self.out.flush()

    # ------------------------------------------------------------------ synthetic records
    def closed_set(self, rng):
        for _ in range(50):
            k = rng.randrange(self.n)
            S = mask(rng.sample(range(self.n), k))
            U = self.Da.closure(S)
            if U != self.R:
                return U
        U = self.Da.closure(0)
        return U if U != self.R else 0

    def records(self, size, rng):
        out = []
        for _ in range(size):
            t = rng.choice(self.templates)
            U = self.closed_set(rng)
            r = []
            for a in range(self.n):
                if (U >> a) & 1:
                    r.append(t[a])
                else:
                    self.fresh += 1
                    r.append("~%d" % self.fresh)
            out.append(r)
        return out

    # ------------------------------------------------------------------ tables, indexes, triggers
    def build(self, mode, design):
        t0 = time.time()
        self.drop_tables()
        info = {"schemata": len(design), "unique": 0, "indexes": 0, "key_triggers": 0, "fd_triggers": 0}
        cur = self.cur
        for i, sch in enumerate(design):
            table = "%s_%s_%d" % (self.name, mode, i)
            cols = [self.cols[a] for a in sch["attrs"]]
            cur.execute("CREATE TABLE e3w.%s ENGINE=InnoDB AS SELECT DISTINCT %s FROM %s" % (q(table), ", ".join(q(c) for c in cols), self.src))
            self.tables.append((table, cols))
            keys = [[self.cols[a] for a in K] for K in sch["keys"]]
            fds = [([self.cols[a] for a in X], self.cols[A]) for X, A in (sch.get("fds") or [])]
            stmts, inf = enforcement_statements(table, keys, fds, self.types, lhs_index=self.lhs_index)
            for s in stmts:
                cur.execute(s)
            for k in inf:
                info[k] += inf[k]
        self.con.commit()
        info["build_seconds"] = time.time() - t0
        return info

    def drop_tables(self):
        for table, _ in self.tables:
            self.cur.execute("DROP TABLE IF EXISTS e3w.%s" % q(table))
        self.con.commit()
        self.tables = []

    def restore(self):
        """delete the synthetic rows (every inserted row carries a fresh value)"""
        for table, cols in self.tables:
            self.cur.execute("DELETE FROM e3w.%s WHERE %s" % (q(table), " OR ".join("%s LIKE '~%%'" % q(c) for c in cols)))
        self.con.commit()

    # ------------------------------------------------------------------ the measurement
    def insert(self, recs):
        cur = self.cur
        stmts = [(table, "INSERT IGNORE INTO e3w.%s (%s) VALUES (%s)" % (q(table), ", ".join(q(c) for c in cols), ", ".join(["%s"] * len(cols))),
                  [self.cols.index(c) for c in cols]) for table, cols in self.tables]
        inserted = 0
        t0 = time.time()
        for b in range(0, len(recs), BATCH):
            batch = recs[b:b + BATCH]
            for table, sql, idx in stmts:
                rows = [tuple(r[i] for i in idx) for r in batch]
                cur.executemany(sql, rows)
                inserted += cur.rowcount
        self.con.commit()
        return time.time() - t0, inserted

    def run_mode(self, mode, design, loss):
        t_mode = time.time()
        for size in self.sizes:
            if time.time() - t_mode > self.budget:
                self.write(dict(set=self.name, mode=mode, truncated="budget of %d s exhausted before size %d" % (self.budget, size)))
                self.log(mode, "budget exhausted before size", size)
                break
            info = self.build(mode, design)
            if size == self.sizes[0]:
                self.write(dict(set=self.name, mode=mode, design=True, loss=loss, rows=self.rows, lhs_index=self.lhs_index, **info))
                self.log(mode, "design:", info)
            for rep in range(self.reps):
                if rep > 0 and time.time() - t_mode > self.budget:
                    self.write(dict(set=self.name, mode=mode, size=size, truncated="budget of %d s exhausted after %d repetitions" % (self.budget, rep)))
                    self.log(mode, size, "budget exhausted after", rep, "repetitions")
                    break
                rng = random.Random(1000003 * size + 7919 * rep + MODES.index(mode))
                recs = self.records(size, rng)
                if rep > 0:
                    self.restore()
                try:
                    secs, inserted = self.insert(recs)
                except pymysql.err.OperationalError as e:
                    self.con.rollback()
                    self.write(dict(set=self.name, mode=mode, size=size, rep=rep, error=str(e.args[:2])))
                    self.log(mode, size, rep, "ERROR", e.args[:2])
                    return
                self.write(dict(set=self.name, mode=mode, size=size, rep=rep, seconds=round(secs, 3), inserted=inserted,
                                attempted=size * len(design), lhs_index=self.lhs_index))
                self.log(mode, size, rep, "%.2fs" % secs, "%d rows" % inserted)
        self.drop_tables()

    def run(self, modes):
        designs = self.rec["designs"]
        done = {}
        for mode in modes:
            if mode == "keys" and designs.get("orig"):
                d = [dict(attrs=s["attrs"], keys=s["keys"], fds=[]) for s in designs["orig"]]
            elif mode not in designs or designs[mode] is None:
                self.write(dict(set=self.name, mode=mode, skipped="no design"))
                continue
            else:
                d = designs[mode]
            if any(s.get("fds") is None and mode in ("orig", "3nf") for s in d):
                self.write(dict(set=self.name, mode=mode, skipped="trigger FDs not computed"))
                continue
            dup = next((m for m in done if same_design(done[m], d)), None)
            if dup is not None:
                self.write(dict(set=self.name, mode=mode, skipped="same design as " + dup, same_as=dup))
                self.log(mode, "same design as", dup)
                continue
            done[mode] = d
            loss = {"orig": 0, "keys": self.rec.get("nu"), "3nf": self.rec.get("3nf_loss"), "bcnf": self.rec.get("bcnf_loss"),
                    "repair": self.rec.get("repair_loss"), "drop": self.rec.get("drop_loss")}[mode]
            self.run_mode(mode, d, loss)
        self.out.close()

# ---------------------------------------------------------------------- checks and tables
def check(name):
    """the minimal cover of Sigma and the minimal keys hold on the source table"""
    rec = e1_record(name)
    n = rec["n"]
    con = connect(autocommit=True)
    cur = con.cursor()
    bad = 0
    orig = rec["designs"]["orig"][0]
    for X, A in orig["fds"] or []:
        cols = ["c%d" % a for a in X]
        group = ("GROUP BY " + ", ".join(q(c) for c in cols)) if cols else ""   # an empty left-hand side: a constant column
        cur.execute("SELECT 1 FROM e3.%s %s HAVING COUNT(DISTINCT %s) > 1 LIMIT 1" % (q(name), group, q("c%d" % A)))
        if cur.fetchone():
            bad += 1
            print("  violated: %s -> %s" % (",".join(cols), "c%d" % A))
    for K in orig["keys"]:
        cols = ["c%d" % a for a in K]
        cur.execute("SELECT 1 FROM e3.%s GROUP BY %s HAVING COUNT(*) > 1 LIMIT 1" % (q(name), ", ".join(q(c) for c in cols)))
        if cur.fetchone():
            bad += 1
            print("  key violated: %s" % ",".join(cols))
    print("%s: %d FDs and %d keys checked, %d violated" % (name, len(orig["fds"] or []), len(orig["keys"]), bad), flush=True)
    con.close()

def table():
    import statistics
    for name in SETS:
        f = os.path.join(HERE, "results", "e3_%s.jsonl" % name)
        if not os.path.isfile(f):
            continue
        recs = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
        print("==", name)
        for mode in MODES:
            d = [r for r in recs if r.get("mode") == mode and r.get("design")]
            sk = [r for r in recs if r.get("mode") == mode and r.get("skipped")]
            if sk:
                print("  %-7s %s" % (mode, sk[-1]["skipped"]))
                continue
            if not d:
                continue
            d = d[-1]
            cells = []
            for size in sorted(set(r["size"] for r in recs if r.get("mode") == mode and "seconds" in r)):
                xs = [r["seconds"] for r in recs if r.get("mode") == mode and r.get("size") == size and "seconds" in r]
                cells.append("%6d: %8.2fs (n=%d)" % (size, statistics.mean(xs), len(xs)))
            print("  %-7s loss %5s | %3d schemata, %3d UNIQUE, %3d indexes, %3d key triggers, %4d FD triggers | %s" % (
                mode, d.get("loss"), d["schemata"], d["unique"], d["indexes"], d["key_triggers"], d["fd_triggers"], "  ".join(cells)))

def main():
    args = sys.argv[1:]
    sizes, reps, modes, lhs_index, parallel, budget = [10000, 20000, 30000], 5, MODES, True, 0, 7200
    names = []
    i = 0
    action = "run"
    while i < len(args):
        a = args[i]
        if a == "--sizes":
            sizes = [int(x) for x in args[i + 1].split(",")]; i += 2
        elif a == "--reps":
            reps = int(args[i + 1]); i += 2
        elif a == "--budget":
            budget = int(args[i + 1]); i += 2
        elif a == "--modes":
            modes = args[i + 1].split(","); i += 2
        elif a == "--noindex":
            lhs_index = False; i += 1
        elif a == "--parallel":
            parallel = int(args[i + 1]); i += 2
        elif a == "--check":
            action = "check"; i += 1
        elif a == "--table":
            action = "table"; i += 1
        else:
            names.append(a); i += 1
    names = names or list(SETS)
    os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
    if action == "table":
        table()
        return
    if action == "check":
        for name in names:
            check(name)
        return
    if parallel:
        opts = ["--sizes", ",".join(map(str, sizes)), "--reps", str(reps), "--modes", ",".join(modes), "--budget", str(budget)] + ([] if lhs_index else ["--noindex"])
        running = {}
        todo = list(names)
        while todo or running:
            while todo and len(running) < parallel:
                name = todo.pop(0)
                log = open(os.path.join(HERE, "results", "e3_%s.log" % name), "a")
                running[name] = subprocess.Popen([sys.executable, os.path.abspath(__file__)] + opts + [name], stdout=log, stderr=subprocess.STDOUT)
                print(time.strftime("%H:%M:%S"), "started", name, flush=True)
            time.sleep(5)
            for name, p in list(running.items()):
                if p.poll() is not None:
                    print(time.strftime("%H:%M:%S"), "finished", name, "exit", p.returncode, flush=True)
                    del running[name]
        return
    for name in names:
        rec = e1_record(name)
        n, Da = atomic(name)
        con = connect()
        h = Harness(name, con, rec, n, Da, sizes, reps, lhs_index=lhs_index, budget=budget)
        h.log("start: %d rows, %d templates, sizes %s, reps %d, modes %s, lhs_index %s, budget %d s per mode" % (h.rows, len(h.templates), sizes, reps, modes, lhs_index, budget))
        h.run(modes)
        con.close()

if __name__ == "__main__":
    main()
