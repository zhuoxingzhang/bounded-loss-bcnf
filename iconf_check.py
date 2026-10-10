r"""iconf_check.py: compares the Python port of iCONF (iconf.py) with its Java implementation on every FD set of
experiments.py; one line per set with the numbers of schemata, the losses of the two designs (all minimal keys
declared) and the running times.

usage: python3 iconf_check.py [name-filter]      results/iconf_check.log
"""
import sys, time
import experiments as e
from fdlib import atomic_cover, load_any, keyed, key_dependencies, loss_of, FDSet
from iconf import iconf_decomposition, iconf_java

flt = sys.argv[1] if len(sys.argv) > 1 else None
for name, path in e.SETS:
    if flt and flt not in name:
        continue
    n, F, _ = load_any(path)
    if len(F) > e.ASSUME_ATOMIC_ABOVE:
        Da = FDSet(n, sorted(set(F.fds)))
    else:
        Da = atomic_cover(F, cap=e.MAX_MINIMAL)
    t = time.time()
    dp = iconf_decomposition(n, Da)
    tp = time.time() - t
    dj, tj = iconf_java(n, Da)
    lp = loss_of(Da, key_dependencies(n, keyed(Da, dp)))
    lj = loss_of(Da, key_dependencies(n, keyed(Da, dj)))
    print("%-22s |Da|=%6d  same=%s  |D| py=%d java=%d  loss py=%d java=%d  time py=%.1fs java=%.1fs"
          % (name, len(Da), set(dp) == set(dj), len(dp), len(dj), lp, lj, tp, tj), flush=True)
