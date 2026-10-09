r"""triggers.py: enforcing FDs and keys in MySQL (experiment E3).

A key K of a schema S is enforced by a UNIQUE index on K. A non-key FD X -> A of S is enforced by a row-level
trigger: BEFORE INSERT (and BEFORE UPDATE) the trigger looks up a stored tuple that agrees with the new tuple on
X and differs on A, and raises SQLSTATE 45000 if one exists; a secondary index on X makes the lookup a point
query. Every schema gets one trigger per event that checks all of its FDs in turn. On data sets whose FDs were
discovered under the null equality interpretation the comparisons are null-safe (<=>), so two NULLs agree.

Column names are passed as they appear in the table (the FD files refer to columns by index, the caller maps
the indices to names). The generated statements are plain SQL, one statement per list element; CREATE TRIGGER
statements contain BEGIN ... END blocks and must be executed as single statements (a driver does that; the
command-line client needs DELIMITER).
"""

def q(name):
    return "`%s`" % name

def _eq(a, b, nullsafe):
    return "%s <=> %s" % (a, b) if nullsafe else "%s = %s" % (a, b)

def _neq(a, b, nullsafe):
    return "NOT (%s <=> %s)" % (a, b) if nullsafe else "%s <> %s" % (a, b)

def fd_lookup(table, X, A, nullsafe, exclude=None):
    """SELECT that finds a stored tuple agreeing with NEW on X and disagreeing on A"""
    conds = [_eq("t." + q(x), "NEW." + q(x), nullsafe) for x in X]
    conds.append(_neq("t." + q(A), "NEW." + q(A), nullsafe))
    if exclude is not None:
        conds.append("NOT (t.%s <=> OLD.%s)" % (q(exclude), q(exclude)))
    return "SELECT 1 FROM %s t WHERE %s LIMIT 1" % (q(table), " AND ".join(conds))

def trigger_statements(table, fds, nullsafe=True, id_col=None, update=True):
    """CREATE TRIGGER statements enforcing the FDs (list of (X, A) with column names) on the table"""
    if not fds:
        return []
    out = []
    for event, suffix in (("INSERT", "ins"), ("UPDATE", "upd")):
        if event == "UPDATE" and not update:
            continue
        body = []
        for i, (X, A) in enumerate(fds):
            look = fd_lookup(table, X, A, nullsafe, exclude=id_col if event == "UPDATE" else None)
            body.append("  IF EXISTS (%s) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'FD %d of %s violated'; END IF;" % (look, i, table))
        out.append("CREATE TRIGGER %s BEFORE %s ON %s FOR EACH ROW\nBEGIN\n%s\nEND" % (
            q("%s_fd_%s" % (table, suffix)), event, q(table), "\n".join(body)))
    return out

def drop_trigger_statements(table):
    return ["DROP TRIGGER IF EXISTS %s" % q("%s_fd_%s" % (table, s)) for s in ("ins", "upd")]

def index_statements(table, fds, col_types, prefix=32, max_bytes=3072):
    """CREATE INDEX on the left-hand side of every FD (one index per distinct X); long VARCHAR columns are
    indexed by a prefix so that the index stays within InnoDB's limit of 3072 bytes"""
    out = []
    seen = set()
    for i, (X, A) in enumerate(fds):
        key = tuple(X)
        if key in seen:
            continue
        seen.add(key)
        out.append("CREATE INDEX %s ON %s (%s)" % (q("%s_x%d" % (table, len(seen))), q(table), ", ".join(_indexed(x, col_types, prefix, len(X), max_bytes) for x in X)))
    return out

def unique_statements(table, keys, col_types, prefix=32, max_bytes=3072):
    """ALTER TABLE ... ADD UNIQUE for every minimal key (a prefix index is not allowed for UNIQUE, so long
    VARCHAR key columns are compared through a generated hash column only when needed)"""
    out = []
    for i, K in enumerate(keys):
        cols = []
        for c in K:
            n = _bytes(c, col_types)
            cols.append(q(c))
        total = sum(_bytes(c, col_types) for c in K)
        if total > max_bytes:
            # a UNIQUE index cannot use prefixes; hash the long columns into a generated column
            hcol = "%s_h%d" % (table, i)
            expr = "SHA1(CONCAT_WS(CHAR(31), %s))" % ", ".join("COALESCE(%s, CHAR(0))" % q(c) for c in K)
            out.append("ALTER TABLE %s ADD COLUMN %s CHAR(40) GENERATED ALWAYS AS (%s) STORED" % (q(table), q(hcol), expr))
            out.append("ALTER TABLE %s ADD UNIQUE %s (%s)" % (q(table), q("%s_k%d" % (table, i)), q(hcol)))
        else:
            out.append("ALTER TABLE %s ADD UNIQUE %s (%s)" % (q(table), q("%s_k%d" % (table, i)), ", ".join(cols)))
    return out

def _bytes(col, col_types):
    """index bytes of a column from its MySQL type (utf8mb4 characters count four bytes)"""
    t = col_types.get(col, "varchar(255)").lower()
    if t.startswith("varchar(") or t.startswith("char("):
        n = int(t[t.index("(") + 1:t.index(")")])
        return 4 * n + (2 if t.startswith("varchar") else 0)
    if t.startswith("decimal("):
        return 16
    if t.startswith("bigint"):
        return 8
    if t.startswith("int") or t.startswith("date"):
        return 4
    return 8

def _indexed(col, col_types, prefix, k, max_bytes):
    budget = max_bytes // max(1, k)
    if _bytes(col, col_types) > budget and col_types.get(col, "varchar(255)").lower().startswith(("varchar", "char")):
        return "%s(%d)" % (q(col), min(prefix, max(1, budget // 4)))
    return q(col)

if __name__ == "__main__":
    types = {"0": "varchar(30)", "1": "varchar(30)", "2": "varchar(30)"}
    for s in index_statements("abalone", [(["0", "1"], "2")], types) + unique_statements("abalone", [["0", "1", "2"]], types) + trigger_statements("abalone", [(["0", "1"], "2")], nullsafe=True, id_col="id"):
        print(s + ";")
