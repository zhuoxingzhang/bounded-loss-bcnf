r"""pgdb.py: the connection to the official PostgreSQL build of the experiments (on the server: binaries in
/data/zzha969/pg-official/pg18, socket directory /data/zzha969/pg-official/run, port 55434, database bcnf with
the extension btree_gist and the schemas src and w). PGHOST, PGPORT and PGDATABASE override the defaults.
"""
import os
import psycopg2

HOST = os.environ.get("PGHOST", "/data/zzha969/pg-official/run")
PORT = int(os.environ.get("PGPORT", "55434"))
DB = os.environ.get("PGDATABASE", "bcnf")

def connect(autocommit=False):
    con = psycopg2.connect(host=HOST, port=PORT, dbname=DB)
    con.autocommit = autocommit
    return con

def qi(name):
    """a quoted identifier"""
    return '"%s"' % name.replace('"', '""')
