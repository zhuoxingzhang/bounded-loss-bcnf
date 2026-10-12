r"""e3pg.py: operational overhead of the designs in PostgreSQL (experiment E3 on the official build; runs on the server).

For a data set, every design of E1 (results/e1_<name>.jsonl of experiments.py) is materialised in schema w of the
database bcnf (pgdb.py): one table per schema that holds the distinct projection of the source table src.<set>
(pgload.py), every declared minimal key as a UNIQUE constraint, and in the modes that enforce non-key FDs the
non-key FDs of a minimal cover of every schema (the "fds" of the E1 record) by one of two mechanisms:

  x  (exclusion constraints) EXCLUDE USING gist (x1 WITH =, ..., xk WITH =, a WITH <>) per FD X -> A, from the
     extension btree_gist; every such constraint maintains a GiST index of its own;
  t  (triggers) one BEFORE INSERT row trigger per table in PL/pgSQL that looks up, for every FD X -> A, one stored
     tuple that agrees with the new tuple on X (an index range scan on X: every left-hand side that is not the
     column set of a key gets a B-tree index) and raises an exception if it differs on A. One tuple suffices,
     since the stored relation satisfies the FD. The measurement session disables sequential and bitmap scans,
     so that the lookups use the index: PL/pgSQL caches a generic plan, and the plan chosen while a table is
     small would otherwise keep scanning the table as it grows.

Modes: orig-x (the original relation, every FD enforced), keys (the original relation with its minimal keys only),
3nf-x (iCONF), 3nfc-x (classical 3NF synthesis), bcnf, gbcnf (greedy BCNF, gbcnf.py), repair, drop (keys only). The trigger modes orig-t, 3nf-t
and 3nfc-t are not run by default (--modes selects them), and neither are 3nf and 3nfc, the two 3NF syntheses with
keys only, whose times the trade-off figure of paper_figures.py needs (--modes 3nf,3nfc).
A mode whose tables, keys and enforced FDs equal those of an earlier mode is not measured again.

Then `size` synthetic records are inserted, projected onto every schema (INSERT ... ON CONFLICT DO NOTHING in
batches of 1,000 rows, all batches in one transaction, the commit included in the time). The records depend only
on the set, the size and the repetition, so every mode inserts the same records. A synthetic record copies a
random stored record on a closed set U of attributes (the closure of a random subset, U != R) and carries fresh
values elsewhere, so the enlarged relation satisfies every FD of Sigma and no insertion is rejected. Every
repetition starts from freshly built tables, since deleting the synthetic rows and vacuuming leaves the GiST
indexes of the exclusion constraints larger and slower than freshly built ones. The budget of a mode counts its
insertion time only, and a watchdog cancels the insertion that exhausts it. A repetition whose connection the server
closes is repeated from fresh tables on a new connection (at most RETRIES times; its record notes the retries).

With --copy, the tables of a mode are built once in a database e3t_<set>_<mode> (from e3t_<set>_base, which holds
the extensions and a copy of the source table), and every repetition inserts into a file copy of that database
(CREATE DATABASE ... TEMPLATE ... STRATEGY FILE_COPY) whose tables and indexes are first loaded into the buffer
cache (pg_prewarm). The copy holds the same pages as freshly built tables; this serves the sets on which building
the exclusion constraints takes hours. A template is reused while its design is unchanged (a hash in the comment of
the database), and --prepare builds the templates without measuring, so that several modes can be built in parallel.

usage: python3 e3pg.py [--sizes 10000,20000,30000] [--reps 5] [--modes ...] [--budget 7200] [--parallel K] [--copy] [--out F] [set ...]
       python3 e3pg.py --prepare --modes ... [set ...]   build the templates of --copy
       python3 e3pg.py --check [set ...]      verify the FDs and keys of the original relation on the source tables
       python3 e3pg.py --table                summarise results/e3pg_<set>.jsonl
sets: abalone adult breast bridges echo hepatitis letter ncvoter weather tpch_orders tpch_part
"""
import sys, os, io, json, time, random, hashlib, subprocess, threading, statistics
import psycopg2, psycopg2.extras, psycopg2.errors
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdlib import *
from pgdb import connect, qi
from e3 import SETS, e1_record, atomic, same_design
import experiments

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)   # the repository root, which holds data/, results/ and iconf/
MODES = ["orig-x", "keys", "3nf-x", "3nfc-x", "bcnf", "gbcnf", "repair", "drop"]   # the paper enforces non-key FDs by exclusion constraints
ALL_MODES = ["orig-x", "orig-t", "keys", "3nf-x", "3nf-t", "3nfc-x", "3nfc-t", "bcnf", "gbcnf", "repair", "drop"]   # -t: triggers, on request
BATCH = 1000
TEMPLATE_SEED = 42
MAX_KEY_BYTES = 2000      # a UNIQUE B-tree entry must fit into a third of a page; wider keys get an md5 index
RETRIES = 5               # repetitions repeated after the server closed the connection (terminated from outside)

def design_of(rec, mode):
    """(design, enforcement) of a mode: the schemata with keys and trigger FDs, and 'x', 't' or None"""
    designs = rec["designs"]
    base, _, how = mode.partition("-")
    if base == "keys":
        d = designs.get("orig")
        return (None if d is None else [dict(attrs=s["attrs"], keys=s["keys"], fds=[]) for s in d]), None
    d = designs.get(base)
    if d is None:
        return None, None
    if how:
        return d, how
    return [dict(attrs=s["attrs"], keys=s["keys"], fds=[]) for s in d], None

def loss_of_mode(rec, mode):
    base = mode.partition("-")[0]
    return {"orig": 0, "keys": rec.get("nu"), "3nf": rec.get("3nf_loss"), "3nfc": rec.get("3nfc_loss"),
            "bcnf": rec.get("bcnf_loss"), "gbcnf": rec.get("gbcnf_loss"), "repair": rec.get("repair_loss"), "drop": rec.get("drop_loss")}[base]

class Harness:
    def __init__(self, name, con, rec, n, Da, sizes, reps, budget=7200, verbose=True, copy=False, out=None):
        self.name, self.con, self.rec, self.n, self.Da = name, con, rec, n, Da
        self.sizes, self.reps, self.budget, self.verbose, self.copy = sizes, reps, budget, verbose, copy
        self.cur = con.cursor()
        self.wcon, self.wcur = con, self.cur      # the connection to the database of the tables (a copy with --copy)
        self.R = (1 << n) - 1
        self.src = "src.%s" % qi(name)
        cur = self.cur
        cur.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='src' AND table_name=%s", (name,))
        self.cols = ["c%d" % j for j in experiments.source_columns(SETS[name], cur.fetchone()[0])][:n]   # the columns of the attributes
        assert len(self.cols) == n, (name, n, self.cols)
        cur.execute("SET enable_seqscan = off")
        cur.execute("SET enable_bitmapscan = off")
        cur.execute("SELECT %s FROM %s" % (", ".join("max(octet_length(%s))" % c for c in self.cols), self.src))
        self.width = dict(zip(self.cols, [w or 0 for w in cur.fetchone()]))
        cur.execute("SELECT setseed(%s)", (TEMPLATE_SEED / 100.0,))
        cur.execute("SELECT %s FROM %s ORDER BY random() LIMIT %d" % (", ".join(self.cols), self.src, max(sizes)))
        self.templates = cur.fetchall()
        cur.execute("SELECT count(*) FROM %s" % self.src)
        self.rows = cur.fetchone()[0]
        con.commit()
        self.tables = []
        self.out = open(out or os.path.join(ROOT, "results", "e3pg_%s.jsonl" % name), "a", encoding="utf-8")

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

    def records(self, size, rep):
        """the synthetic records of (size, rep), the same for every mode"""
        rng = random.Random(1000003 * size + 7919 * rep)
        out, fresh = [], 0
        for _ in range(size):
            t = rng.choice(self.templates)
            U = self.closed_set(rng)
            r = []
            for a in range(self.n):
                if (U >> a) & 1:
                    r.append(t[a])
                else:
                    fresh += 1
                    r.append("~%d_%d_%d" % (size, rep, fresh))
            out.append(r)
        return out

    # ------------------------------------------------------------------ tables, constraints, triggers
    def build(self, mode, design, how):
        t0 = time.time()
        self.drop_tables()
        cur = self.wcur
        info = {"schemata": len(design), "unique": 0, "unique_md5": 0, "exclusion": 0, "trigger_fds": 0, "indexes": 0}
        for i, sch in enumerate(design):
            table = "%s_%s_%d" % (self.name, mode.replace("-", "_"), i)
            t = "w.%s" % qi(table)
            cols = [self.cols[a] for a in sch["attrs"]]
            cur.execute("DROP TABLE IF EXISTS %s CASCADE" % t)
            cur.execute("CREATE TABLE %s AS SELECT DISTINCT %s FROM %s" % (t, ", ".join(cols), self.src))
            self.tables.append((table, cols))
            keysets = []
            for j, K in enumerate(sch["keys"]):
                kc = [self.cols[a] for a in K]
                keysets.append(frozenset(kc))
                if not kc:      # the empty key: at most one tuple
                    cur.execute("CREATE UNIQUE INDEX %s ON %s ((true))" % (qi("%s_k%d" % (table, j)), t))
                    info["unique"] += 1
                elif sum(self.width[c] for c in kc) > MAX_KEY_BYTES:
                    cur.execute("CREATE UNIQUE INDEX %s ON %s (md5(ROW(%s)::text))" % (qi("%s_k%d" % (table, j)), t, ", ".join(kc)))
                    info["unique_md5"] += 1
                else:
                    cur.execute("ALTER TABLE %s ADD CONSTRAINT %s UNIQUE (%s)" % (t, qi("%s_k%d" % (table, j)), ", ".join(kc)))
                    info["unique"] += 1
            fds = [([self.cols[a] for a in X], self.cols[A]) for X, A in (sch.get("fds") or [])] if how else []
            if how == "x":
                for j, (X, A) in enumerate(fds):
                    cur.execute("ALTER TABLE %s ADD CONSTRAINT %s EXCLUDE USING gist (%s)" % (
                        t, qi("%s_x%d" % (table, j)), ", ".join(["%s WITH =" % x for x in X] + ["%s WITH <>" % A])))
                    info["exclusion"] += 1
            elif how == "t" and fds:
                lhs = []
                for X, A in fds:
                    if X and frozenset(X) not in keysets and frozenset(X) not in lhs:
                        lhs.append(frozenset(X))
                for j, X in enumerate(lhs):
                    cur.execute("CREATE INDEX %s ON %s (%s)" % (qi("%s_i%d" % (table, j)), t, ", ".join(sorted(X))))
                    info["indexes"] += 1
                body = []
                for X, A in fds:
                    where = (" WHERE " + " AND ".join("s.%s = NEW.%s" % (x, x) for x in X)) if X else ""
                    body.append("  SELECT s.%s INTO v FROM %s s%s LIMIT 1;\n"
                                "  IF FOUND AND v <> NEW.%s THEN RAISE EXCEPTION 'FD %s -> %s violated on %s'; END IF;"
                                % (A, t, where, A, ",".join(X), A, table))
                fn = "w.%s" % qi("%s_fd" % table)
                cur.execute("CREATE OR REPLACE FUNCTION %s() RETURNS trigger LANGUAGE plpgsql AS $f$\nDECLARE v text;\nBEGIN\n%s\n  RETURN NEW;\nEND\n$f$" % (fn, "\n".join(body)))
                cur.execute("CREATE TRIGGER %s BEFORE INSERT ON %s FOR EACH ROW EXECUTE FUNCTION %s()" % (qi("%s_trg" % table), t, fn))
                info["trigger_fds"] += len(fds)
            cur.execute("ANALYZE %s" % t)
        self.wcon.commit()
        info["build_seconds"] = round(time.time() - t0, 3)
        return info

    def drop_tables(self):
        for table, _ in self.tables:
            self.wcur.execute("DROP TABLE IF EXISTS w.%s CASCADE" % qi(table))
            self.wcur.execute("DROP FUNCTION IF EXISTS w.%s()" % qi("%s_fd" % table))
        self.wcon.commit()
        self.tables = []

    # ------------------------------------------------------------------ database copies (--copy)
    def dbname(self, suffix):
        return "e3t_%s_%s" % (self.name, suffix)

    def admin(self, sql, args=None):
        """a statement outside a transaction (CREATE and DROP DATABASE) on a connection of its own"""
        con = connect(autocommit=True)
        try:
            con.cursor().execute(sql, args)
        finally:
            con.close()

    def attach(self, db):
        self.wcon = connect(dbname=db)
        self.wcur = self.wcon.cursor()
        self.wcur.execute("SET enable_seqscan = off")
        self.wcur.execute("SET enable_bitmapscan = off")
        self.wcon.commit()

    def detach(self):
        if self.wcon is not self.con:
            self.wcon.close()
        self.wcon, self.wcur = self.con, self.cur

    def reconnect(self):
        """after the server closed a connection: a new connection to bcnf (the copy of --copy is made afresh)"""
        for con in (self.wcon, self.con):
            if not con.closed:
                con.close()
        self.con = connect()
        self.cur = self.con.cursor()
        self.cur.execute("SET enable_seqscan = off")
        self.cur.execute("SET enable_bitmapscan = off")
        self.con.commit()
        self.wcon, self.wcur = self.con, self.cur

    def base(self):
        """the database e3t_<set>_base with the extensions and a copy of the source table, created once (under an
        advisory lock, since --prepare builds several templates from it in parallel)"""
        db = self.dbname("base")
        cur = self.cur
        cur.execute("SELECT pg_advisory_lock(hashtext(%s))", (db,))
        try:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db,))
            if cur.fetchone():
                return db
            cur.execute("SELECT attname, format_type(atttypid, atttypmod) FROM pg_attribute WHERE attrelid = %s::regclass "
                        "AND attnum > 0 AND NOT attisdropped ORDER BY attnum", (self.src,))
            cols = cur.fetchall()
            buf = io.BytesIO()
            cur.copy_expert("COPY %s TO STDOUT" % self.src, buf)
            self.admin("CREATE DATABASE %s" % qi(db))
            con = connect(dbname=db)
            c = con.cursor()
            for sql in ("CREATE EXTENSION btree_gist", "CREATE EXTENSION pg_prewarm", "CREATE SCHEMA src", "CREATE SCHEMA w"):
                c.execute(sql)
            c.execute("CREATE TABLE %s (%s)" % (self.src, ", ".join("%s %s" % (qi(a), t) for a, t in cols)))
            buf.seek(0)
            c.copy_expert("COPY %s FROM STDIN" % self.src, buf)
            c.execute("ANALYZE %s" % self.src)
            con.commit()
            con.close()
            self.log("created", db)
            return db
        finally:
            cur.execute("SELECT pg_advisory_unlock(hashtext(%s))", (db,))
            self.con.commit()

    def template(self, mode, design, how):
        """(name, build information) of the database e3t_<set>_<mode> that holds the freshly built tables of the mode;
        built unless a complete template of the same design exists (the comment is written after the build)"""
        tag = hashlib.md5(json.dumps([design, how], sort_keys=True).encode()).hexdigest()
        db = self.dbname(mode.replace("-", "_"))
        self.cur.execute("SELECT shobj_description(oid, 'pg_database') FROM pg_database WHERE datname = %s", (db,))
        row = self.cur.fetchone()
        self.con.commit()
        if row and row[0]:
            info = json.loads(row[0])
            if info.pop("tag") == tag:
                self.tables = [(t, c) for t, c in info.pop("tables")]
                self.log(mode, "template", db, "reused")
                return db, info
        if row:
            self.admin("DROP DATABASE %s WITH (FORCE)" % qi(db))
        base = self.base()
        self.admin("CREATE DATABASE %s TEMPLATE %s STRATEGY FILE_COPY" % (qi(db), qi(base)))
        self.attach(db)
        self.tables = []
        info = self.build(mode, design, how)
        self.detach()
        self.admin("COMMENT ON DATABASE %s IS %%s" % qi(db), (json.dumps(dict(info, tag=tag, tables=self.tables)),))
        self.log(mode, "template", db, "built:", info)
        return db, info

    def fresh_copy(self, template):
        """connects to a new file copy of the template with its tables and indexes in the buffer cache; the seconds"""
        t0 = time.time()
        run = self.dbname("run")
        self.admin("DROP DATABASE IF EXISTS %s WITH (FORCE)" % qi(run))
        self.admin("CREATE DATABASE %s TEMPLATE %s STRATEGY FILE_COPY" % (qi(run), qi(template)))
        self.attach(run)
        self.wcur.execute("SELECT count(pg_prewarm(c.oid)) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                          "WHERE n.nspname = 'w' AND c.relkind IN ('r', 'i')")
        self.wcon.commit()
        return time.time() - t0

    def drop_copy(self):
        self.detach()
        self.admin("DROP DATABASE IF EXISTS %s WITH (FORCE)" % qi(self.dbname("run")))

    def release(self):
        """after a mode: drops the tables, or the copy of the template"""
        if self.copy:
            self.drop_copy()
            self.tables = []
        else:
            self.drop_tables()

    # ------------------------------------------------------------------ the measurement
    def insert(self, recs, deadline=None):
        cur = self.wcur
        stmts = [("INSERT INTO w.%s (%s) VALUES %%s ON CONFLICT DO NOTHING" % (qi(table), ", ".join(cols)),
                  [self.cols.index(c) for c in cols]) for table, cols in self.tables]
        self.partial = 0
        inserted = 0
        killer = None
        if deadline is not None:
            killer = threading.Timer(max(1.0, deadline - time.time()), self.wcon.cancel)
            killer.daemon = True
            killer.start()
        t0 = time.time()
        try:
            for b in range(0, len(recs), BATCH):
                batch = recs[b:b + BATCH]
                for sql, idx in stmts:
                    psycopg2.extras.execute_values(cur, sql, [tuple(r[i] for i in idx) for r in batch], page_size=BATCH)
                    inserted += cur.rowcount
                self.partial = inserted
            self.wcon.commit()
        finally:
            if killer is not None:
                killer.cancel()
        return time.time() - t0, inserted

    def run_mode(self, mode, design, how, loss):
        spent = 0.0      # the insertion time of the mode, which the budget bounds
        if self.copy:
            template, info = self.template(mode, design, how)
        for size in self.sizes:
            if spent > self.budget:
                self.write(dict(set=self.name, mode=mode, truncated="budget of %d s exhausted before size %d" % (self.budget, size)))
                self.log(mode, "budget exhausted before size", size)
                break
            for rep in range(self.reps):
                if rep > 0 and spent > self.budget:
                    self.write(dict(set=self.name, mode=mode, size=size, truncated="budget of %d s exhausted after %d repetitions" % (self.budget, rep)))
                    self.log(mode, size, "budget exhausted after", rep, "repetitions")
                    break
                recs = self.records(size, rep)
                for attempt in range(RETRIES + 1):
                    extra = {"retries": attempt} if attempt else {}
                    if self.copy:
                        extra["copy_seconds"] = round(self.fresh_copy(template), 3)
                    else:
                        info = self.build(mode, design, how)
                    if size == self.sizes[0] and rep == 0 and attempt == 0:
                        self.write(dict(set=self.name, mode=mode, design=True, loss=loss, rows=self.rows, copy=self.copy, **info))
                        self.log(mode, "design:", info)
                    t_rep = time.time()
                    try:
                        secs, inserted = self.insert(recs, deadline=t_rep + self.budget - spent)
                        break
                    except psycopg2.errors.QueryCanceled:
                        self.wcon.rollback()
                        elapsed = time.time() - t_rep
                        self.write(dict(set=self.name, mode=mode, size=size, rep=rep, timeout_seconds=round(elapsed, 3),
                                        inserted_before_timeout=self.partial, attempted=size * len(design),
                                        truncated="budget of %d s exhausted during size %d repetition %d" % (self.budget, size, rep), **extra))
                        self.log(mode, size, rep, "TIMEOUT after %.0fs with %d rows of the completed batches" % (elapsed, self.partial))
                        self.release()
                        return
                    except psycopg2.Error as e:
                        if self.wcon.closed and attempt < RETRIES:
                            # the server closed the connection (twice on 2026-10-11 the backend of hepatitis was
                            # terminated by a signal from outside): reconnect and repeat the repetition from fresh tables
                            self.write(dict(set=self.name, mode=mode, size=size, rep=rep, attempt=attempt, connection_lost=str(e)[:300]))
                            self.log(mode, size, rep, "connection lost after %.0fs, repeating: %s" % (time.time() - t_rep, str(e).strip()[:120]))
                            time.sleep(30)
                            self.reconnect()
                            continue
                        if self.wcon.closed:
                            self.reconnect()
                        else:
                            self.wcon.rollback()
                        self.write(dict(set=self.name, mode=mode, size=size, rep=rep, error=str(e)[:300]))
                        self.log(mode, size, rep, "ERROR", str(e)[:300])
                        self.release()
                        return
                spent += secs
                self.write(dict(set=self.name, mode=mode, size=size, rep=rep, seconds=round(secs, 3), inserted=inserted,
                                attempted=size * len(design), **extra))
                self.log(mode, size, rep, "%.2fs" % secs, "%d rows" % inserted,
                         "(copy %.0fs)" % extra["copy_seconds"] if "copy_seconds" in extra else "",
                         "(attempt %d)" % (attempt + 1) if attempt else "")
                if self.copy:
                    self.drop_copy()
        self.release()

    def effective(self, mode):
        """(design with the enforced FDs, enforcement 'x', 't' or None) of a mode, or (None, why it is skipped)"""
        design, how = design_of(self.rec, mode)
        if design is None:
            return None, "no design"
        if how and any(s.get("fds") is None for s in design):
            return None, "trigger FDs not computed"
        enforced = design if how else [dict(s, fds=[]) for s in design]
        return enforced, (how if how and any(s.get("fds") for s in design) else None)

    def prepare(self, modes):
        for mode in modes:
            enforced, how_eff = self.effective(mode)
            if enforced is not None:
                self.template(mode, enforced, how_eff)
        self.out.close()

    def run(self, modes):
        done = {}
        for mode in modes:
            enforced, how_eff = self.effective(mode)
            if enforced is None:
                self.write(dict(set=self.name, mode=mode, skipped=how_eff))
                continue
            dup = next((m for m, (d, h) in done.items() if h == how_eff and same_design(d, enforced)), None)
            if dup is not None:
                self.write(dict(set=self.name, mode=mode, skipped="same design as " + dup, same_as=dup))
                self.log(mode, "same design as", dup)
                continue
            done[mode] = (enforced, how_eff)
            self.run_mode(mode, enforced, how_eff, loss_of_mode(self.rec, mode))
        self.out.close()

# ---------------------------------------------------------------------- checks and tables
def check(name):
    """the minimal cover of Sigma and the minimal keys hold on the source table"""
    rec = e1_record(name)
    con = connect(autocommit=True)
    cur = con.cursor()
    bad = 0
    orig = rec["designs"]["orig"][0]
    cur.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema='src' AND table_name=%s", (name,))
    col = ["c%d" % j for j in experiments.source_columns(SETS[name], cur.fetchone()[0])]   # attribute -> column
    for X, A in orig["fds"] or []:
        cols = [col[a] for a in X]
        group = ("GROUP BY " + ", ".join(cols)) if cols else ""
        cur.execute("SELECT 1 FROM src.%s %s HAVING count(DISTINCT %s) > 1 LIMIT 1" % (qi(name), group, col[A]))
        if cur.fetchone():
            bad += 1
            print("  violated: %s -> %s" % (",".join(cols), col[A]))
    for K in orig["keys"]:
        cols = [col[a] for a in K]
        if not cols:
            continue
        cur.execute("SELECT 1 FROM src.%s GROUP BY %s HAVING count(*) > 1 LIMIT 1" % (qi(name), ", ".join(cols)))
        if cur.fetchone():
            bad += 1
            print("  key violated: %s" % ",".join(cols))
    print("%s: %d FDs and %d keys checked, %d violated" % (name, len(orig["fds"] or []), len(orig["keys"]), bad), flush=True)
    con.close()

def summary(recs, mode, size):
    xs = [r["seconds"] for r in recs if r.get("mode") == mode and r.get("size") == size and "seconds" in r]
    return xs

def table():
    for name in SETS:
        f = os.path.join(ROOT, "results", "e3pg_%s.jsonl" % name)
        if not os.path.isfile(f):
            continue
        recs = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
        print("==", name)
        for mode in ALL_MODES:
            sk = [r for r in recs if r.get("mode") == mode and r.get("skipped")]
            if sk:
                print("  %-7s %s" % (mode, sk[-1]["skipped"]))
                continue
            d = [r for r in recs if r.get("mode") == mode and r.get("design")]
            if not d:
                continue
            d = d[-1]
            cells = []
            for size in sorted(set(r["size"] for r in recs if r.get("mode") == mode and "seconds" in r)):
                xs = summary(recs, mode, size)
                sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
                cells.append("%6d: %8.2fs +- %.2f (n=%d)" % (size, statistics.mean(xs), sd, len(xs)))
            to = [r for r in recs if r.get("mode") == mode and "timeout_seconds" in r]
            if to:
                cells.append("TIMEOUT at size %d" % to[-1]["size"])
            print("  %-7s loss %5s | %4d schemata, %4d UNIQUE (+%d md5), %4d EXCLUDE, %4d trigger FDs, %4d indexes | %s" % (
                mode, d.get("loss"), d["schemata"], d["unique"], d["unique_md5"], d["exclusion"], d["trigger_fds"], d["indexes"], "  ".join(cells)))

def main():
    args = sys.argv[1:]
    sizes, reps, modes, parallel, budget, copy, out = [10000, 20000, 30000], 5, MODES, 0, 7200, False, None
    names, action, i = [], "run", 0
    while i < len(args):
        a = args[i]
        if a == "--copy":
            copy = True; i += 1
        elif a == "--prepare":
            action, copy = "prepare", True; i += 1
        elif a == "--out":
            out = args[i + 1]; i += 2
        elif a == "--sizes":
            sizes = [int(x) for x in args[i + 1].split(",")]; i += 2
        elif a == "--reps":
            reps = int(args[i + 1]); i += 2
        elif a == "--budget":
            budget = int(args[i + 1]); i += 2
        elif a == "--modes":
            modes = args[i + 1].split(","); i += 2
        elif a == "--parallel":
            parallel = int(args[i + 1]); i += 2
        elif a == "--check":
            action = "check"; i += 1
        elif a == "--table":
            action = "table"; i += 1
        else:
            names.append(a); i += 1
    names = names or [s for s in SETS if s != "fdred"]
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    if action == "table":
        table()
        return
    if action == "check":
        for name in names:
            check(name)
        return
    if parallel:
        opts = ["--sizes", ",".join(map(str, sizes)), "--reps", str(reps), "--modes", ",".join(modes), "--budget", str(budget)] + (["--copy"] if copy else [])
        running, todo = {}, list(names)
        while todo or running:
            while todo and len(running) < parallel:
                name = todo.pop(0)
                log = open(os.path.join(ROOT, "results", "e3pg_%s.log" % name), "a")
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
        h = Harness(name, con, rec, n, Da, sizes, reps, budget=budget, copy=copy, out=out)
        if action == "prepare":
            h.prepare(modes)
        else:
            h.log("start: %d rows, %d templates, sizes %s, reps %d, modes %s, budget %d s per mode%s" % (
                h.rows, len(h.templates), sizes, reps, modes, budget, ", copies of the built tables" if copy else ""))
            h.run(modes)
        con.close()

if __name__ == "__main__":
    main()
