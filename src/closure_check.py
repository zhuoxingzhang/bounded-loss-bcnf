r"""closure_check.py: the C closures of fdlib (closure.c) against the Python reference (FDLIB_PYTHON=1).

Run once per implementation; each run writes a digest of deterministic results on every FD set of E1 that the
budget of the 3NF syntheses admits: the atomic cover, iConf, DecompAlg4, the classical BCNF decomposition, the
uncritical fixpoint and the deterministic greedy of drop.py, and closures with disabled FDs and recorded firings for
random queries (fixed seed). The two digests must be equal.

usage: python3 closure_check.py out.json; FDLIB_PYTHON=1 python3 closure_check.py out_py.json; then compare
"""
import sys, json, random, time, hashlib
import experiments as e
import fdlib
from fdlib import load_any, FDSet, bcnf_decomposition, minimal_keys
from iconf import iconf_decomposition, decomp4
from drop import uncritical_fixpoint, greedy_plain

def digest(x):
    return hashlib.sha1(json.dumps(x, sort_keys=True).encode()).hexdigest()

out = {"c": fdlib._C is not None}
t0 = time.time()
for name in [s[0] for s in e.SETS]:
    if name in ("diabetic(null)", "fd-red"):
        continue
    t = time.time()
    n, F, _ = load_any(e.fd_path(name))
    Da, _ = e.sigma_a(n, F)
    R = (1 << n) - 1
    rng = random.Random(7)
    rec = {"cover": digest(sorted(Da.fds)), "keys": digest(sorted(minimal_keys(Da, R)))}
    rec["iconf"] = digest(sorted(map(str, iconf_decomposition(n, Da))))
    rec["decomp4"] = digest(sorted(map(str, decomp4(n, Da))))
    rec["bcnf"] = digest(sorted(map(str, bcnf_decomposition(Da, R))))
    m = len(Da.fds)
    q = []
    for _ in range(2000):
        X = rng.getrandbits(n) & rng.getrandbits(n)
        dis = set(rng.sample(range(m), rng.randint(0, min(m, 50))))
        r = []
        q.append((Da.closure_without(X, dis, r), r))
    rec["without"] = digest(q)
    if m <= 600:
        st = {}
        fx = uncritical_fixpoint(n, Da, None, R, None, st)
        rec["fixpoint"] = digest(sorted(fx[0]) if fx else None)
        g = greedy_plain(n, Da, None, R, None, st)
        rec["greedy"] = digest(sorted(g[0]) if g else None)
    rec["seconds"] = round(time.time() - t, 1)
    out[name] = rec
    print(name, rec, flush=True)
with open(sys.argv[1], "w") as f:
    json.dump(out, f, indent=1)
print("total %.0fs" % (time.time() - t0))
