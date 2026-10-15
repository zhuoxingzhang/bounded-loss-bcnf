r"""diag_fallback.py: where does Repair's fallback spend its time on the large FD sets?

Runs the stages of Repair on one FD set with timing: the 3NF decomposition of iCONF, the local Drops (with their
budget), the atomic cover of Gamma, the enforceability test, the greedy on Gamma_a and the greedy on Sigma_a.

usage: python3 diag_fallback.py <name> [local_time=120] [greedy_time=300]
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fdlib import *
from iconf import iconf_decomposition
from drop import drop, greedy_plain, greedy_restarts, uncritical_fixpoint
from experiments import SETS, ASSUME_ATOMIC_ABOVE, MAX_MINIMAL, max_extra_for

def main():
    name = sys.argv[1]
    local_time = float(sys.argv[2]) if len(sys.argv) > 2 else 120
    greedy_time = float(sys.argv[3]) if len(sys.argv) > 3 else 300
    path = dict(SETS)[name]
    n, F, _ = load_any(path)
    t0 = time.time()
    if len(F) > ASSUME_ATOMIC_ABOVE:
        Da = FDSet(n, sorted(set(F.fds)))
    else:
        Da = atomic_cover(F, cap=MAX_MINIMAL)
    R = (1 << n) - 1
    print("%s: n=%d |Da|=%d (%.1fs)" % (name, n, len(Da), time.time() - t0), flush=True)
    t = time.time()
    dec0 = iconf_decomposition(n, Da)
    crit = [S for S in dec0 if not is_bcnf(Da, S)]
    print("iCONF: %d schemata, %d critical (%.1fs)" % (len(dec0), len(crit), time.time() - t), flush=True)
    # local Drops
    gamma = []
    t = time.time()
    nfail = 0
    for S in dec0:
        DaS = Da.restrict(S)
        if is_bcnf(Da, S):
            for K in minimal_keys(DaS, S):
                for b in bits(S & ~K):
                    gamma.append((K, b))
        else:
            r = drop(n, DaS, None, R=S, time_limit=local_time, max_w=4, max_extra=max_extra_for(n))
            if r.design is None:
                nfail += 1
                for K in minimal_keys(DaS, S):
                    for b in bits(S & ~K):
                        gamma.append((K, b))
            else:
                gamma += key_dependencies(n, r.design).fds
    print("local Drops done: |Gamma|=%d, %d schemata without design (%.1fs)" % (len(gamma), nfail, time.time() - t), flush=True)
    G = FDSet(n, gamma)
    t = time.time()
    Ga = atomic_cover(G)
    print("atomic cover of Gamma: %d minimal FDs (%.1fs)" % (len(Ga), time.time() - t), flush=True)
    t = time.time()
    ok, U = enforceable(Ga)
    unc, cr = split_critical(Ga)
    print("enforceable: %s, uncritical %d, critical %d (%.1fs)" % (ok, len(unc), len(cr), time.time() - t), flush=True)
    print("loss of Gamma on Sigma_a:", loss_of(Da, G), flush=True)
    for label, Xa in (("Gamma_a", Ga), ("Sigma_a", Da)):
        stats = {}
        t = time.time()
        fx = uncritical_fixpoint(n, Xa, None, R, t + greedy_time, stats)
        print("fixpoint on %s: %s (%.1fs) stats=%s" % (label, "None" if fx is None else "|Delta|=%d" % len(fx[0]), time.time() - t, stats), flush=True)
        if fx is not None:
            d0 = design_from_cover(fx[2], fx[3], R)
            print("   design: %d schemata, loss on Sigma_a %d" % (len(d0), loss_of(Da, key_dependencies(n, d0))), flush=True)
    # greedy on Gamma_a
    stats = {}
    t = time.time()
    g = greedy_plain(n, Ga, None, R, t + greedy_time, stats)
    print("greedy on Gamma_a: %s (%.1fs) stats=%s" % ("None" if g is None else "|Delta|=%d" % len(g[0]), time.time() - t, stats), flush=True)
    if g is not None:
        d1 = design_from_cover(g[2], g[3], R)
        print("   design: %d schemata, loss on Sigma_a %d" % (len(d1), loss_of(Da, key_dependencies(n, d1))), flush=True)
    # greedy on Sigma_a
    stats = {}
    t = time.time()
    g = greedy_plain(n, Da, None, R, t + greedy_time, stats)
    print("greedy on Sigma_a: %s (%.1fs) stats=%s" % ("None" if g is None else "|Delta|=%d" % len(g[0]), time.time() - t, stats), flush=True)
    if g is not None:
        d1 = design_from_cover(g[2], g[3], R)
        print("   design: %d schemata, loss on Sigma_a %d" % (len(d1), loss_of(Da, key_dependencies(n, d1))), flush=True)

if __name__ == "__main__":
    main()
