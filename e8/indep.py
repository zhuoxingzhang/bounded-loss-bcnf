"""Independence of key designs under the weak-instance model: chase-based consistency of states."""
import sys, random, itertools
sys.path.insert(0, sys.argv[1] if len(sys.argv) > 1 else ".")
from minloss import table


def chase_consistent(N, design, state):
    """design: list of (S mask, [K masks]); state: list of lists of tuples (dict attr->value) per schema."""
    rows = []
    nid = 0
    for (S, keys), rel in zip(design, state):
        for t in rel:
            row = []
            for a in range(N):
                if (S >> a) & 1:
                    row.append(("c", t[a]))
                else:
                    row.append(("n", nid)); nid += 1
            rows.append(row)
    deps = [(K, S) for S, keys in design for K in keys]
    changed = True
    while changed:
        changed = False
        for K, S in deps:
            kattrs = [a for a in range(N) if (K >> a) & 1]
            sattrs = [a for a in range(N) if (S >> a) & 1]
            groups = {}
            for row in rows:
                groups.setdefault(tuple(row[a] for a in kattrs), []).append(row)
            for g in groups.values():
                if len(g) < 2:
                    continue
                for a in sattrs:
                    vals = {row[a] for row in g}
                    if len(vals) < 2:
                        continue
                    consts = {v for v in vals if v[0] == "c"}
                    if len(consts) > 1:
                        return False
                    target = next(iter(consts)) if consts else min(vals)
                    nulls = {v for v in vals if v != target}
                    for row in rows:
                        for b in range(N):
                            if row[b] in nulls:
                                row[b] = target
                    changed = True
                if changed:
                    break
            if changed:
                break
    return True


def local_ok(S, keys, rel):
    for K in keys:
        seen = {}
        for t in rel:
            k = tuple(t[a] for a in range(32) if (K >> a) & 1)
            s = tuple(t[a] for a in range(32) if (S >> a) & 1)
            if seen.setdefault(k, s) != s:
                return False
    return True


def uniqueness(N, design):
    for i, (S, keys) in enumerate(design):
        others = [(K, b) for j, (T, ks) in enumerate(design) if j != i for K in ks for b in range(N) if (T >> b) & 1]
        cl = table(N, others)
        for a in range(N):
            if (S >> a) & 1 and (cl[S & ~(1 << a)] >> a) & 1:
                return False
    return True


def random_state(rng, N, design, maxt=2, dom=2):
    state = []
    for S, keys in design:
        rel = []
        for _ in range(rng.randint(1, maxt)):
            t = {a: rng.randrange(dom) for a in range(N) if (S >> a) & 1}
            if local_ok(S, keys, rel + [t]):
                rel.append(t)
        state.append(rel)
    return state


def lookup_conflict(N, design, order="any"):
    """Exact test candidate: from each schema S, lookups of other schemas by declared keys.
    order='any': explore all lookup orders (DFS); order='first': canonical order only."""
    for i, (S, _) in enumerate(design):
        start = (S, frozenset([i]))
        stack = [start]; seen = set()
        while stack:
            known, used = stack.pop()
            if (known, used) in seen:
                continue
            seen.add((known, used))
            for j, (T, keys) in enumerate(design):
                if j in used:
                    continue
                ks = [K for K in keys if K & known == K]
                if ks:
                    if any((T & ~K) & known for K in ks):
                        return True
                    stack.append((known | T, used | {j}))
                if order == "first" and stack and stack[-1][1] != used:
                    break
    return False
