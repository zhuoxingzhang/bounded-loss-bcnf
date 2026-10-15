r"""decomp4_check.py: compares the Python port of DecompAlg4 (iconf.decomp4), the classical 3NF synthesis of E1 to E4,
with its Java original (iconf/Decomp4Driver.java) on the atomic cover of E1, in its order, of every FD set with
designs in E1 and of the documented sets; one line per set with the numbers of schemata, the losses of the two designs
(all minimal keys declared) and the running times.

usage: python3 decomp4_check.py [name ...]      results/decomp4_check.log
"""
import sys, os, json, time
import experiments as e
from fdlib import load_any, keyed, key_dependencies, loss_of
from iconf import decomp4, decomp4_java

def has_designs(name):
    f = os.path.join(e.ROOT, "results", "e1_%s.jsonl" % e.safe(name))
    if not os.path.isfile(f):
        return False
    recs = [json.loads(l) for l in open(f, encoding="utf-8") if l.strip()]
    return bool(recs) and "designs" in recs[-1]

names = sys.argv[1:] or [name for name in [s for s, _ in e.SETS] + list(e.DOCUMENTED) if has_designs(name)]
for name in names:
    n, F, _ = load_any(e.fd_path(name))
    Da, _ = e.sigma_a(n, F)
    t = time.time()
    dp = decomp4(n, Da)
    tp = time.time() - t
    dj, tj = decomp4_java(n, Da)
    lp = loss_of(Da, key_dependencies(n, keyed(Da, dp)))
    lj = loss_of(Da, key_dependencies(n, keyed(Da, dj)))
    print("%-22s |Da|=%6d  same=%s  |D| py=%d java=%d  loss py=%d java=%d  time py=%.1fs java=%.1fs"
          % (name, len(Da), set(dp) == set(dj), len(dp), len(dj), lp, lj, tp, tj), flush=True)
