"""q2ctx.py with a given state limit and the faster searches of conp_fast.py: complete_full and complete_restricted of
minloss pop the same states in the same order, but compute the closure table of a child from its parent's table,
skip a set of generators that was popped before, and store a visited table as bytes. Output lines as in q2ctx.py.
usage: python q2ctx_fast.py <dir of q2ctx.py> <contexts> <limit> <workers> run <log> [log ...]
           the masks that the logs list as stopped by the limit or do not list
       python q2ctx_fast.py <dir of q2ctx.py> <contexts> <limit> <workers> check <log> [log ...]
           the masks that the logs list as finished, compared with the logs"""
import sys, ast, array
src = open(sys.argv[1] + "/q2ctx.py", encoding="utf-8").read()
exec(src.split('if __name__=="__main__":')[0])
import minloss
LIMIT = int(sys.argv[3])


def extend(N, cl, X, a):
    """the closure table of F + [(X, a)] from the closure table cl of F"""
    bit = 1 << a
    return [cl[c | bit] if c & X == X and not c & bit else c for c in cl]


def fd_key(gens):
    return bytes(b for X, a in sorted(gens) for b in (X & 255, X >> 8, a))


def search(N, Psi, Delta, children):
    seen, popped = set(), set()
    stack = [(list(Psi), None, None)]
    while stack:
        gens, parent, f = stack.pop()
        g = fd_key(gens)
        if g in popped:
            continue
        popped.add(g)
        cl = table(N, gens) if parent is None else extend(N, parent, *f)
        key = array.array("H", cl).tobytes()
        if key in seen:
            continue
        seen.add(key)
        if len(seen) > LIMIT:
            raise RuntimeError("limit")
        if hits(cl, Delta):
            continue
        ok, mins, unc, bad = analyse(N, cl)
        if ok:
            return gens
        for h in children(cl, bad):
            stack.append((gens + [h], cl, h))
    return None


def complete_full(N, Psi, Delta, limit=None):
    return search(N, Psi, Delta, lambda cl, bad: [(Xp, a) for X, a in Delta for Xp in weakenings(N, X, a, cl[bad[0][0]])
                                                  if not (cl[Xp] >> a) & 1])


def complete_restricted(N, Psi, Delta, L, limit=None):
    return search(N, Psi, Delta, lambda cl, bad: [(Xp, a) for Xp, a in L if not (cl[Xp] >> a) & 1])


minloss.complete_full, minloss.complete_restricted = complete_full, complete_restricted


def logged(logs):
    out = {}
    for log in logs:
        for line in open(log, encoding="utf-8"):
            if line.startswith("["):
                i = line.index("]") + 1
                rest = line[i:].strip()
                out[sum(1 << base.index(f) for f in ast.literal_eval(line[:i]))] = ast.literal_eval(rest[:rest.rindex(")") + 1])
    return out


if __name__ == "__main__":
    old = logged(sys.argv[6:])
    check = sys.argv[5] == "check"
    masks = [m for m in range(64) if (m in old and old[m][1] != "limit") == check]
    print("# %s %d masks with limit %d" % (sys.argv[5], len(masks), LIMIT), flush=True)
    differ = 0
    with Pool(int(sys.argv[4])) as p:
        for r in p.imap_unordered(job, masks):
            m = r[0]; flag = "  <== local>full" if len(r) > 4 and r[2] is not None and r[4] != r[2] else ""
            if check and tuple(r[1:]) != tuple(old[m]):
                differ += 1; flag += "  <== differs from the log: %r" % (old[m],)
            print([base[j] for j in range(6) if (m >> j) & 1], r[1:], flag, flush=True)
    if check:
        print("# %d of %d masks differ from the log" % (differ, len(masks)), flush=True)
