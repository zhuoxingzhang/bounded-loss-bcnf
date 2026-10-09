r"""triggers.py: enforcing keys and FDs in MySQL (experiments E3 and E4).

A key K of a schema S is enforced by a UNIQUE index on K. A non-key FD X -> A of S is enforced by a row-level
trigger: BEFORE INSERT (and BEFORE UPDATE) the trigger looks up a stored tuple that agrees with the new tuple on
X and differs on A, and raises SQLSTATE 45000 if one exists. Every schema gets one trigger per event that checks
all of its FDs in turn. The lookup on X is an index range scan: the columns of the UNIQUE indexes are ordered so
that as many left-hand sides as possible are prefixes of a key index, and the remaining left-hand sides get a
plain secondary index each (plan_indexes). Without an index on X the lookup scans the table.

InnoDB allows 64 secondary indexes per table and 3072 bytes per index: keys beyond the index budget are enforced
by a trigger lookup as well (key_statements with triggers), long VARCHAR columns of plain indexes are indexed by
a prefix, and a UNIQUE index that would exceed the byte limit is declared on a generated SHA1 column instead.

On data sets whose FDs were discovered under the null equality interpretation the comparisons are null-safe
(<=>), so two NULLs agree; the E3 tables keep the missing-value marker '?' as a string, where '=' does the same.

Column names are passed as they appear in the table. The generated statements are plain SQL, one statement per
list element; CREATE TRIGGER statements contain BEGIN ... END blocks and must be executed as single statements
(a driver does that; the command-line client needs DELIMITER).
"""

MAX_INDEXES = 64        # secondary indexes per InnoDB table
MAX_INDEX_BYTES = 3072  # bytes per index
MAX_INDEX_COLS = 16     # columns per index

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

def key_lookup(table, K, nullsafe, exclude=None):
    """SELECT that finds a stored tuple agreeing with NEW on the key K"""
    conds = [_eq("t." + q(x), "NEW." + q(x), nullsafe) for x in K]
    if exclude is not None:
        conds.append("NOT (t.%s <=> OLD.%s)" % (q(exclude), q(exclude)))
    return "SELECT 1 FROM %s t WHERE %s LIMIT 1" % (q(table), " AND ".join(conds))

def trigger_statements(table, fds, keys=(), nullsafe=False, id_col=None, update=True):
    """CREATE TRIGGER statements enforcing the FDs (list of (X, A) with column names) and the keys (lists of
    column names) on the table"""
    if not fds and not keys:
        return []
    out = []
    for event, suffix in (("INSERT", "ins"), ("UPDATE", "upd")):
        if event == "UPDATE" and not update:
            continue
        excl = id_col if event == "UPDATE" else None
        body = []
        for i, K in enumerate(keys):
            look = key_lookup(table, K, nullsafe, exclude=excl)
            body.append("  IF EXISTS (%s) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'key %d of %s violated'; END IF;" % (look, i, table))
        for i, (X, A) in enumerate(fds):
            look = fd_lookup(table, X, A, nullsafe, exclude=excl)
            body.append("  IF EXISTS (%s) THEN SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'FD %d of %s violated'; END IF;" % (look, i, table))
        out.append("CREATE TRIGGER %s BEFORE %s ON %s FOR EACH ROW\nBEGIN\n%s\nEND" % (
            q("%s_fd_%s" % (table, suffix)), event, q(table), "\n".join(body)))
    return out

def drop_trigger_statements(table):
    return ["DROP TRIGGER IF EXISTS %s" % q("%s_fd_%s" % (table, s)) for s in ("ins", "upd")]

def plan_indexes(keys, lhss):
    """Order the columns of the UNIQUE index of every key, and choose extra plain indexes, so that every
    left-hand side X of a trigger-enforced FD is a prefix (as a set of columns) of some index.
    Returns (unique_cols, extra_cols): ordered column lists for the keys (same order as keys) and for the
    extra indexes."""
    need = set(frozenset(x) for x in lhss if x)
    covered = set()
    def order(S, pool):
        # grow a chain of nested left-hand sides inside S, smallest first; each becomes a prefix of the index
        prefix = frozenset()
        out = []
        while True:
            cands = [T for T in pool if T <= S and prefix < T]
            if not cands:
                break
            T = min(cands, key=lambda T: (len(T), sorted(T)))
            out += sorted(T - prefix)
            covered.add(T)
            prefix = T
        out += sorted(S - prefix)
        return out
    uniques = [order(frozenset(K), need) for K in keys]
    extras = []
    for X in sorted(need, key=lambda T: (-len(T), sorted(T))):
        if X not in covered:
            extras.append(order(X, need))
    return uniques, extras

def index_statements(table, indexes, col_types, prefix=32, max_bytes=MAX_INDEX_BYTES):
    """CREATE INDEX for every ordered column list; long VARCHAR columns are indexed by a prefix so that the
    index stays within InnoDB's byte limit"""
    out = []
    for i, cols in enumerate(indexes):
        cols = cols[:MAX_INDEX_COLS]
        out.append("CREATE INDEX %s ON %s (%s)" % (q("%s_x%d" % (table, i)), q(table),
                                                   ", ".join(_indexed(c, col_types, prefix, len(cols), max_bytes) for c in cols)))
    return out

def unique_statements(table, keys, col_types, max_bytes=MAX_INDEX_BYTES):
    """ALTER TABLE ... ADD UNIQUE for every key (ordered column list). A UNIQUE index cannot use prefixes, so a
    key beyond the byte limit is enforced through a generated SHA1 column of its concatenated values."""
    out = []
    for i, K in enumerate(keys):
        total = sum(_bytes(c, col_types) for c in K)
        if total > max_bytes or len(K) > MAX_INDEX_COLS:
            hcol = "%s_h%d" % (table, i)
            expr = "SHA1(CONCAT_WS(CHAR(31), %s))" % ", ".join("COALESCE(%s, CHAR(0))" % q(c) for c in K)
            out.append("ALTER TABLE %s ADD COLUMN %s CHAR(40) GENERATED ALWAYS AS (%s) STORED" % (q(table), q(hcol), expr))
            out.append("ALTER TABLE %s ADD UNIQUE %s (%s)" % (q(table), q("%s_k%d" % (table, i)), q(hcol)))
        else:
            out.append("ALTER TABLE %s ADD UNIQUE %s (%s)" % (q(table), q("%s_k%d" % (table, i)), ", ".join(q(c) for c in K)))
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

def enforcement_statements(table, keys, fds, col_types, nullsafe=False, lhs_index=True, max_indexes=MAX_INDEXES):
    """All statements that enforce the keys (lists of columns) and the FDs ((X, A) with column names) on the
    table, within the index budget: UNIQUE indexes for the keys (as many as fit), plain indexes for the
    left-hand sides not covered by a key index (when lhs_index), triggers for the FDs and for the keys beyond
    the budget. Returns (statements, info) with the counts."""
    uniques, extras = plan_indexes(keys, [X for X, A in fds] if lhs_index else [])
    n_unique = min(len(uniques), max_indexes)
    key_triggers = keys[n_unique:]
    uniques = uniques[:n_unique]
    extras = extras[:max(0, max_indexes - n_unique)] if lhs_index else []
    stmts = unique_statements(table, uniques, col_types) + index_statements(table, extras, col_types)
    stmts += trigger_statements(table, fds, keys=key_triggers, nullsafe=nullsafe, update=False)
    info = {"unique": n_unique, "indexes": len(extras), "key_triggers": len(key_triggers), "fd_triggers": len(fds)}
    return stmts, info

if __name__ == "__main__":
    types = {"0": "varchar(30)", "1": "varchar(30)", "2": "varchar(30)", "3": "varchar(30)"}
    s, info = enforcement_statements("abalone", [["0", "1", "2"]], [(["0", "1"], "3"), (["1"], "2")], types)
    for x in s:
        print(x + ";")
    print(info)
