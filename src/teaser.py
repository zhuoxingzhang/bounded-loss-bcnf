r"""teaser.py: update overheads of the designs of the running example (Figure in the introduction; runs on the server).

The schema is R = {C, S, T, Z} with Sigma = {C -> ST, ST -> Z, Z -> T}. A synthetic address book with `base`
customers is generated: towns, zip codes with a fixed town per zip (Z -> T), streets with a fixed zip per street
and town (ST -> Z), and customers with a unique id and a random address (C -> ST). The designs are materialised
in MySQL and `size` new customers are inserted (projected onto the schemata, INSERT IGNORE in batches of 1,000,
one transaction), reps times per size:

  D1+triggers  CSTZ with key C, the FDs ST -> Z and Z -> T enforced by triggers (every FD enforced, no decomposition)
  3NF+trigger  the 3NF synthesis {STZ (keys ST, SZ), CST (key C)} with Z -> T enforced by a trigger (iConf's output)
  D1           CSTZ with key C only (vendor guidance, loss 2)
  D2           ZT (Z), CSZ (C): classical BCNF decomposition (loss 1)
  D4           STZ (ST, SZ), CST (C): the BCNF design with loss 1 that enforces the business key ST

Half of the new customers move to an existing address (the lookups of the triggers hit), the other half to a new
street of an existing town with a new zip code, so that every FD remains satisfied.

usage: python3 teaser.py [--base 100000] [--sizes 10000,20000,30000] [--reps 5]       results/mysql/teaser.jsonl
"""
import sys, os, json, time, random
try:
    import pymysql   # the MySQL runs only; teaser_pg.py and teaser_risk.py import World without it
except ImportError:
    pymysql = None
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from triggers import enforcement_statements, q

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)   # the repository root, which holds data/, results/ and iconf/
SOCK = os.environ.get("MYSQL_SOCKET", "/tmp/mysql.sock")   # the Unix socket of the MySQL server that holds the source tables
COLS = ["C", "S", "T", "Z"]
TYPES = {c: "varchar(24)" for c in COLS}
DESIGNS = {
    # name: list of (table, attrs, keys, trigger FDs)
    "D1+triggers": [("t_cstz", "CSTZ", ["C"], [("ST", "Z"), ("Z", "T")])],
    "3NF+trigger": [("t_stz", "STZ", ["ST", "SZ"], [("Z", "T")]), ("t_cst", "CST", ["C"], [])],
    "D1": [("t_cstz", "CSTZ", ["C"], [])],
    "D2": [("t_zt", "ZT", ["Z"], []), ("t_csz", "CSZ", ["C"], [])],
    "D4": [("t_stz", "STZ", ["ST", "SZ"], []), ("t_cst", "CST", ["C"], [])],
}

class World:
    """towns, zips with a town, streets with a zip per (street, town)"""
    def __init__(self, rng, towns=200, zips_per_town=10, streets_per_town=50):
        self.rng = rng
        self.town_of_zip = {}
        self.zips_of_town = {}
        for t in range(towns):
            town = "town%d" % t
            self.zips_of_town[town] = []
            for z in range(zips_per_town):
                zip_ = "%05d" % (t * zips_per_town + z)
                self.town_of_zip[zip_] = town
                self.zips_of_town[town].append(zip_)
        self.zip_of_address = {}
        self.addresses = []
        for town in self.zips_of_town:
            for s in range(streets_per_town):
                self.new_street(town, "street%d" % s)
        self.next_street = streets_per_town
        self.next_zip = len(self.town_of_zip)

    def new_street(self, town, street):
        zip_ = self.rng.choice(self.zips_of_town[town])
        self.zip_of_address[(street, town)] = zip_
        self.addresses.append((street, town))
        return street, town, zip_

    def new_street_new_zip(self, town):
        """a new street of the town with a brand-new zip code of that town"""
        zip_ = "%05d" % self.next_zip
        self.next_zip += 1
        self.town_of_zip[zip_] = town
        self.zips_of_town[town].append(zip_)
        street = "nstreet%d" % self.next_street
        self.next_street += 1
        self.zip_of_address[(street, town)] = zip_
        self.addresses.append((street, town))
        return street, town, zip_

    def customers(self, k, start, fresh_share=0.5):
        out = []
        for i in range(k):
            if self.rng.random() < fresh_share:
                town = self.rng.choice(list(self.zips_of_town))
                s, t, z = self.new_street_new_zip(town)
            else:
                s, t = self.rng.choice(self.addresses)
                z = self.zip_of_address[(s, t)]
            out.append(("cust%d" % (start + i), s, t, z))
        return out

def main():
    args = sys.argv[1:]
    base, sizes, reps = 100000, [10000, 20000, 30000], 5
    i = 0
    while i < len(args):
        if args[i] == "--base":
            base = int(args[i + 1]); i += 2
        elif args[i] == "--sizes":
            sizes = [int(x) for x in args[i + 1].split(",")]; i += 2
        elif args[i] == "--reps":
            reps = int(args[i + 1]); i += 2
        else:
            i += 1
    con = pymysql.connect(unix_socket=SOCK, user="root", database="e3w", autocommit=False, charset="utf8mb4")
    cur = con.cursor()
    out = open(os.path.join(ROOT, "results", "mysql", "teaser.jsonl"), "a", encoding="utf-8")
    for name, tables in DESIGNS.items():
        for size in sizes:
            for rep in range(reps):
                rng = random.Random(1000 * size + rep)
                world = World(rng)
                basedata = world.customers(base, 0)
                # build the tables with the base data
                for table, attrs, keys, fds in tables:
                    cur.execute("DROP TABLE IF EXISTS %s" % q(table))
                    cur.execute("CREATE TABLE %s (%s) ENGINE=InnoDB" % (q(table), ", ".join("%s VARCHAR(24) NOT NULL" % q(a) for a in attrs)))
                    idx = [COLS.index(a) for a in attrs]
                    rows = sorted(set(tuple(r[j] for j in idx) for r in basedata))
                    cur.executemany("INSERT INTO %s (%s) VALUES (%s)" % (q(table), ", ".join(q(a) for a in attrs), ", ".join(["%s"] * len(attrs))), rows)
                    stmts, info = enforcement_statements(table, [list(K) for K in keys], [(list(X), A) for X, A in fds], TYPES)
                    for s in stmts:
                        cur.execute(s)
                con.commit()
                newdata = world.customers(size, base)
                stmts = [(table, "INSERT IGNORE INTO %s (%s) VALUES (%s)" % (q(table), ", ".join(q(a) for a in attrs), ", ".join(["%s"] * len(attrs))), [COLS.index(a) for a in attrs]) for table, attrs, keys, fds in tables]
                t0 = time.time()
                inserted = 0
                for b in range(0, size, 1000):
                    batch = newdata[b:b + 1000]
                    for table, sql, idx in stmts:
                        cur.executemany(sql, [tuple(r[j] for j in idx) for r in batch])
                        inserted += cur.rowcount
                con.commit()
                secs = time.time() - t0
                rec = dict(design=name, base=base, size=size, rep=rep, seconds=round(secs, 3), inserted=inserted)
                out.write(json.dumps(rec) + "\n")
                out.flush()
                print(time.strftime("%H:%M:%S"), name, size, rep, "%.2fs" % secs, inserted, "rows", flush=True)
        for table, attrs, keys, fds in tables:
            cur.execute("DROP TABLE IF EXISTS %s" % q(table))
        con.commit()
    out.close()
    con.close()

if __name__ == "__main__":
    main()
