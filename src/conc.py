r"""conc.py: the designs of E3 under concurrent insertions (runs on the server; a supplementary measurement).

e3pg.py inserts the synthetic records of a data set in one transaction from one client. Here C clients insert the
same records concurrently, in transactions of T records each (every transaction projects its records onto every
table of the design with INSERT ... ON CONFLICT DO NOTHING, as in e3pg.py). The records are
those of e3pg.py (Harness.records), split round-robin over the clients, so every design and every C inserts the
same records. A synthetic record copies a stored record on a closed set U of attributes and carries fresh values
elsewhere, so no insertion conflicts with another one: a projection inside U already exists and is skipped without a
lock, and a projection with a fresh value is new, so the clients lock no shared row.

Every run starts from a file copy of a prewarmed template of the design (the --copy machinery of e3pg.py, in
databases conc_<set>_<mode>). It reports the wall time from the start signal until the last client has committed,
the commit latencies, the MultiXacts and the WAL bytes the cluster consumed during the run, and the wait events of
the clients, sampled every 50 ms from pg_stat_activity. Runs are interleaved (repetition, clients, mode) so that a
change of the server load hits every mode alike.

usage: python3 conc.py [--clients 1,4,16,64] [--txn 10] [--records 20000] [--reps 3] [--modes ...] [--zipf S] [set ...]
       records in results/conc_<set>.jsonl (--out F)
       python3 conc.py --table [set ...]
"""
import sys, os, json, time, threading, statistics, collections, random
import multiprocessing as mp
import psycopg2, psycopg2.extras
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdlib import *
from pgdb import connect, qi
from e3 import SETS, e1_record, atomic, same_design
import e3pg

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODES = ["keys", "3nf", "repair", "drop", "3nf-x"]
SAMPLE = 0.05


class Harness(e3pg.Harness):
    """the harness of e3pg.py with databases of its own (conc_<set>_<suffix>), so that it never touches the
    templates of E3"""
    def dbname(self, suffix):
        return "conc_%s_%s" % (self.name, suffix)


def worker(dbname, stmts, recs, txn, ready, go, out, wid):
    con = connect(dbname=dbname)
    cur = con.cursor()
    cur.execute("SET application_name = 'conc'")
    cur.execute("SET enable_seqscan = off")
    cur.execute("SET enable_bitmapscan = off")
    con.commit()
    ready.put(wid)
    go.wait()
    lat, n, err = [], 0, None
    t0 = time.perf_counter()
    try:
        for b in range(0, len(recs), txn):
            batch = recs[b:b + txn]
            t = time.perf_counter()
            for sql, idx in stmts:
                psycopg2.extras.execute_values(cur, sql, [tuple(r[i] for i in idx) for r in batch], page_size=len(batch))
            con.commit()
            lat.append(time.perf_counter() - t)
            n += len(batch)
    except psycopg2.Error as e:
        err = str(e).strip()[:300]
        try:
            con.rollback()
        except psycopg2.Error:
            pass
    out.put((wid, n, time.perf_counter() - t0, lat, err))
    con.close()


def cluster_counters(cur):
    """(MultiXacts consumed so far, WAL position) of the cluster: mxid_age of a fixed horizon grows with every
    MultiXact the cluster assigns"""
    cur.execute("SELECT mxid_age(datminmxid) FROM pg_database WHERE datname = 'template1'")
    mx = int(cur.fetchone()[0])
    cur.execute("SELECT pg_current_wal_lsn() - '0/0'::pg_lsn")
    return mx, int(cur.fetchone()[0])


def sampler(stop, counts, nsamples):
    con = connect(autocommit=True)
    cur = con.cursor()
    while not stop.is_set():
        cur.execute("SELECT state, coalesce(wait_event_type, 'CPU'), coalesce(wait_event, '') FROM pg_stat_activity "
                    "WHERE application_name = 'conc'")
        for state, wtype, wev in cur.fetchall():
            counts[(state or "", wtype, wev)] += 1
        nsamples[0] += 1
        time.sleep(SAMPLE)
    con.close()


def one_run(h, mode, clients, txn, recs, template):
    """inserts recs from `clients` processes into a fresh copy of the template; the record of the run"""
    copy_seconds = h.fresh_copy(template)
    run_db = h.dbname("run")
    stmts = [("INSERT INTO w.%s (%s) VALUES %%s ON CONFLICT DO NOTHING" % (qi(table), ", ".join(cols)),
              [h.cols.index(c) for c in cols]) for table, cols in h.tables]
    h.detach()      # the parent keeps no connection to the copy while the clients run
    ctx = mp.get_context("fork")
    ready, out, go = ctx.Queue(), ctx.Queue(), ctx.Event()
    procs = [ctx.Process(target=worker, args=(run_db, stmts, recs[w::clients], txn, ready, go, out, w), daemon=True)
             for w in range(clients)]
    for p in procs:
        p.start()
    for _ in procs:
        ready.get(timeout=120)
    mcon = connect(autocommit=True)
    mcur = mcon.cursor()
    mx0, wal0 = cluster_counters(mcur)
    counts, nsamples, stop = collections.Counter(), [0], threading.Event()
    th = threading.Thread(target=sampler, args=(stop, counts, nsamples), daemon=True)
    th.start()
    t0 = time.perf_counter()
    go.set()
    res = [out.get() for _ in procs]
    secs = time.perf_counter() - t0
    stop.set()
    th.join()
    mx1, wal1 = cluster_counters(mcur)
    mcon.close()
    for p in procs:
        p.join(timeout=60)
    h.drop_copy()
    lat = sorted(x for r in res for x in r[3])
    n = sum(r[1] for r in res)
    errors = [r[4] for r in res if r[4]]
    q = lambda f: round(lat[min(len(lat) - 1, int(f * len(lat)))] * 1000, 3) if lat else None
    waits = {"%s|%s|%s" % k: round(v / max(1, nsamples[0]), 3) for k, v in counts.most_common()}
    return dict(seconds=round(secs, 3), records=n, throughput=round(n / secs, 1), lat_ms_p50=q(0.5), lat_ms_p99=q(0.99),
                multixacts=mx1 - mx0, wal_bytes=wal1 - wal0, samples=nsamples[0], waits=waits,
                copy_seconds=round(copy_seconds, 3), errors=errors[:3], failed_clients=len(errors))


def run(name, clients_list, txn, nrec, reps, modes, zipf, out_path):
    rec = e1_record(name)
    n, Da = atomic(name)
    con = connect()
    h = Harness(name, con, rec, n, Da, [nrec], 1, copy=True, out=os.devnull)
    out = open(out_path or os.path.join(ROOT, "results", "conc_%s.jsonl" % name), "a", encoding="utf-8")
    write = lambda r: (out.write(json.dumps(r) + "\n"), out.flush())
    # the templates, one per distinct design
    plan, done = [], {}
    for mode in modes:
        enforced, how = h.effective(mode)
        if enforced is None:
            write(dict(set=name, mode=mode, skipped=how))
            continue
        dup = next((m for m, (d, hw) in done.items() if hw == how and same_design(d, enforced)), None)
        if dup is not None:
            write(dict(set=name, mode=mode, skipped="same design as " + dup))
            h.log(mode, "same design as", dup)
            continue
        done[mode] = (enforced, how)
        template, info = h.template(mode, enforced, how)
        tables = list(h.tables)
        write(dict(set=name, mode=mode, design=True, loss=e3pg.loss_of_mode(rec, mode), **info))
        plan.append((mode, template, tables))
    h.log("templates ready:", [m for m, _, _ in plan])
    for rep in range(reps):
        recs = h.records(nrec, rep)
        if zipf > 0:
            # the stored record of every synthetic record drawn again from a Zipf distribution over the templates,
            # so that a few stored records are copied by many synthetic
            # records; the copied set U and the fresh values stay those of e3pg.py
            rng = random.Random(7 + rep)
            w = [1.0 / (i + 1) ** zipf for i in range(len(h.templates))]
            hot = rng.choices(range(len(h.templates)), weights=w, k=len(recs))
            recs2 = []
            for r, j in zip(recs, hot):
                t = h.templates[j]
                recs2.append([t[a] if not str(r[a]).startswith("~") else r[a] for a in range(n)])
            recs = recs2
        for clients in clients_list:
            order = list(plan)
            random.Random(1000 * rep + clients).shuffle(order)
            for mode, template, tables in order:
                h.tables = list(tables)
                try:
                    r = one_run(h, mode, clients, txn, recs, template)
                except Exception as e:
                    h.log(mode, clients, rep, "ERROR", str(e)[:200])
                    write(dict(set=name, mode=mode, clients=clients, txn=txn, rep=rep, zipf=zipf, error=str(e)[:300]))
                    try:
                        h.reconnect()
                    except Exception:
                        pass
                    continue
                write(dict(set=name, mode=mode, clients=clients, txn=txn, rep=rep, zipf=zipf, **r))
                top = ", ".join("%s %.1f" % (k, v) for k, v in list(r["waits"].items())[:3])
                h.log(mode, "C=%d rep %d: %.2fs, %.0f rec/s, p99 %.1f ms, %d MultiXacts, %.0f MB WAL | %s%s" % (
                    clients, rep, r["seconds"], r["throughput"], r["lat_ms_p99"] or 0, r["multixacts"], r["wal_bytes"] / 1e6, top,
                    " | %d clients FAILED" % r["failed_clients"] if r["failed_clients"] else ""))
    out.close()
    con.close()


def table(names):
    for name in names:
        p = os.path.join(ROOT, "results", "conc_%s.jsonl" % name)
        if not os.path.isfile(p):
            continue
        recs = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
        runs = [r for r in recs if "throughput" in r]
        print("==", name)
        for key in sorted({(r["txn"], r.get("zipf", 0)) for r in runs}):
            txn, z = key
            print("  transactions of %d records, zipf %g" % (txn, z))
            modes = [m for m in MODES if any(r["mode"] == m for r in runs)]
            print("    %8s | %s" % ("clients", " | ".join("%-24s" % m for m in modes)))
            for c in sorted({r["clients"] for r in runs if (r["txn"], r.get("zipf", 0)) == key}):
                cells = []
                for m in modes:
                    rs = [r for r in runs if r["mode"] == m and r["clients"] == c and (r["txn"], r.get("zipf", 0)) == key]
                    if not rs:
                        cells.append("%-24s" % "-")
                        continue
                    tp = statistics.mean(r["throughput"] for r in rs)
                    mx = statistics.mean(r["multixacts"] for r in rs)
                    p99 = statistics.mean(r["lat_ms_p99"] or 0 for r in rs)
                    cells.append("%-24s" % ("%7.0f/s p99 %5.1f mx %d" % (tp, p99, mx)))
                print("    %8d | %s" % (c, " | ".join(cells)))


def main():
    args = sys.argv[1:]
    clients, txn, nrec, reps, modes, zipf, out, names, i = [1, 4, 16, 64], 10, 20000, 3, MODES, 0.0, None, [], 0
    do_table = False
    while i < len(args):
        a = args[i]
        if a == "--clients":
            clients = [int(x) for x in args[i + 1].split(",")]; i += 2
        elif a == "--txn":
            txn = int(args[i + 1]); i += 2
        elif a == "--records":
            nrec = int(args[i + 1]); i += 2
        elif a == "--reps":
            reps = int(args[i + 1]); i += 2
        elif a == "--modes":
            modes = args[i + 1].split(","); i += 2
        elif a == "--zipf":
            zipf = float(args[i + 1]); i += 2
        elif a == "--out":
            out = args[i + 1]; i += 2
        elif a == "--table":
            do_table = True; i += 1
        else:
            names.append(a); i += 1
    names = names or ["abalone", "breast", "bridges", "echo", "ncvoter"]
    if do_table:
        table(names)
        return
    for name in names:
        run(name, clients, txn, nrec, reps, modes, zipf, out)


if __name__ == "__main__":
    main()
