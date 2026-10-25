"""conp_check.py on chosen formulas (1-based indices into its list of 20), one process per formula: the same search
as minloss.complete_full with the same limit, except that a visited closure table is stored as bytes instead of a
tuple of ints (the same set of states in about a twentieth of the memory).
usage: python conp_one.py <dir of conp_check.py and minloss.py> i [j ...]"""
import sys, array
sys.path.insert(0, sys.argv[1])
import minloss
from minloss import table, hits, analyse, weakenings


def complete_full(N, Psi, Delta, limit=200000):
    seen = set()
    stack = [list(Psi)]
    while stack:
        gens = stack.pop()
        cl = table(N, gens)
        key = array.array("H", cl).tobytes()
        if key in seen:
            continue
        seen.add(key)
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
                stack.append(gens + [(Xp, a)])
    return None


minloss.complete_full = complete_full
src = open(sys.argv[1] + "/conp_check.py", encoding="utf-8").read()
last = "print(all([check(n,c) for n,c in tests]))"
assert src.rstrip().endswith(last)
picked = [int(i) for i in sys.argv[2:]]
code = src.rstrip()[:-len(last)].replace("sys.path.insert(0, sys.argv[1])", "")
code += "\nfor i in %r:\n    print('formula', i, end=': ', flush=True)\n" % picked
code += "    try:\n        print('passed' if check(*tests[i - 1]) else 'FAILED', flush=True)\n"
code += "    except RuntimeError as e:\n        print('search', e, flush=True)\n"
exec(compile(code, "conp_check.py", "exec"), {"__name__": "__main__"})
