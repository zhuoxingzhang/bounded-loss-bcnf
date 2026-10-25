"""conp_check.py on chosen formulas (1-based indices into its list of 20) with a given state limit, by the search of
minloss.complete_full made faster without changing it: the states are popped in the same order and the same
closure tables are counted against the limit, but the closure table of a child (its parent's generators plus one
FD) is computed from the parent's table, a set of generators that was popped before is skipped before its table is
computed (its table was seen), and a visited table is stored as bytes.
With --digest, a visited table is stored as its 128-bit BLAKE2b digest and kept as an array of 16-bit closures while
its children wait, and the popped generator sets are not stored (their tables are skipped as seen), so that a state
costs about 100 bytes instead of several kilobytes; two distinct tables share a digest with probability below 1e-20
for 10^8 tables.
usage: python conp_fast.py <dir of conp_check.py and minloss.py> <limit> [--digest] i [j ...]
       python conp_fast.py <dir> test        (the incremental tables against minloss.table on random FD sets)"""
import sys, array, random, time, hashlib
sys.path.insert(0, sys.argv[1])
import minloss
from minloss import table, hits, analyse, weakenings

STATS = {}


def extend(N, cl, X, a):
    """the closure table of F + [(X, a)] from the closure table cl of F: the closure of Y grows by a, and then under
    F, iff X lies in the closure of Y under F and a does not"""
    bit = 1 << a
    return [cl[c | bit] if c & X == X and not c & bit else c for c in cl]


def fd_key(gens):
    return bytes(b for X, a in sorted(gens) for b in (X & 255, X >> 8, a))


def complete_full(N, Psi, Delta, limit=200000, digest=False):
    seen, popped = set(), set()
    stack = [(list(Psi), None, None)]   # (generators, the parent's table, the added FD)
    t0 = time.time()
    while stack:
        gens, parent, f = stack.pop()
        if not digest:
            g = fd_key(gens)
            if g in popped:
                continue
            popped.add(g)
        cl = table(N, gens) if parent is None else extend(N, parent, *f)
        key = array.array("H", cl).tobytes()
        if digest:
            cl = array.array("H", cl)
            key = hashlib.blake2b(key, digest_size=16).digest()
        if key in seen:
            continue
        seen.add(key)
        STATS.update(states=len(seen), seconds=time.time() - t0)
        if len(seen) % 1000000 == 0:
            print("%d closure tables, %d waiting (%.0f s)" % (len(seen), len(stack), time.time() - t0), file=sys.stderr, flush=True)
        if len(seen) > limit:
            raise RuntimeError("limit")
        if hits(cl, Delta):
            continue
        ok, mins, unc, bad = analyse(N, cl)
        if ok:
            return gens
        Y, B = bad[0]
        for X, a in Delta:
            for Xp in weakenings(N, X, a, cl[Y]):
                if (cl[Xp] >> a) & 1:
                    continue
                stack.append((gens + [(Xp, a)], cl, (Xp, a)))
    return None


if sys.argv[2] == "test":
    rng = random.Random(1)
    for trial in range(2000):
        N = rng.randint(3, 11)
        F = [(sum(1 << rng.randrange(N) for _ in range(rng.randint(1, 3))), rng.randrange(N)) for _ in range(rng.randint(0, 12))]
        X, a = sum(1 << rng.randrange(N) for _ in range(rng.randint(1, 3))), rng.randrange(N)
        assert extend(N, table(N, F), X, a) == table(N, F + [(X, a)]), (N, F, X, a)
    print("incremental tables equal minloss.table on 2,000 random FD sets")
    sys.exit()
limit = int(sys.argv[2])
digest = sys.argv[3] == "--digest"
minloss.complete_full = lambda N, Psi, Delta: complete_full(N, Psi, Delta, limit, digest)
src = open(sys.argv[1] + "/conp_check.py", encoding="utf-8").read()
last = "print(all([check(n,c) for n,c in tests]))"
assert src.rstrip().endswith(last)
ns = {"__name__": "__main__"}
exec(compile(src.rstrip()[:-len(last)].replace("sys.path.insert(0, sys.argv[1])", ""), "conp_check.py", "exec"), ns)
for i in [int(i) for i in sys.argv[4 if digest else 3:]]:
    print("formula", i, end=": ", flush=True)
    STATS.clear()
    try:
        r = "passed" if ns["check"](*ns["tests"][i - 1]) else "FAILED"
    except RuntimeError as e:   # the plain half of the check still decides
        n, clauses = ns["tests"][i - 1]
        N, F, attrs, ix = ns["build"](n, clauses)
        Psi = [f for f in minloss.minimal_fds(N, table(N, F)) if f != (1 << ix["T"], ix["Z"])]
        plain, s = analyse(N, table(N, Psi))[0], ns["sat"](n, clauses)
        r = "search %s (sat=%s plain_realizable=%s %s)" % (e, s, plain, "OK" if plain == (not s) else "FAIL")
    print(r, "(%d closure tables, %.0f s)" % (STATS.get("states", 0), STATS.get("seconds", 0)), flush=True)
