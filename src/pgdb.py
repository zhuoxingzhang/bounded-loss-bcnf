r"""pgdb.py: the connection to the PostgreSQL build of the experiments (an unmodified PostgreSQL 18.4 with the
extension btree_gist; the database holds the source tables in the schema src and the designs in the schema w).
The environment variables PGHOST (a host name or the directory of the Unix socket), PGPORT and PGDATABASE select
the server and the database; the defaults are localhost, 5432 and bcnf.
"""
import os
import psycopg2

HOST = os.environ.get("PGHOST", "localhost")
PORT = int(os.environ.get("PGPORT", "5432"))
DB = os.environ.get("PGDATABASE", "bcnf")

def connect(autocommit=False, dbname=None):
    con = psycopg2.connect(host=HOST, port=PORT, dbname=dbname or DB)
    con.autocommit = autocommit
    return con

def qi(name):
    """a quoted identifier"""
    return '"%s"' % name.replace('"', '""')
