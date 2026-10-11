"""Which stage of E1 exceeds the budget on the largest FD sets: time the minimal keys, the 3NF synthesis and the
enforceability test of Sigma+ with a cap per stage.  Usage: python3 diag_timeout.py <name> [cap_seconds]"""
import sys, time, signal
from fdlib import load_any, minimal_keys, synthesize_3nf, enforceable, CapExceeded
import experiments

name = sys.argv[1]
cap = int(sys.argv[2]) if len(sys.argv) > 2 else 600
path = dict(experiments.SETS)[name]
n, F, _ = load_any(path)
R = (1 << n) - 1
print("%s: %d attributes, %d FDs in the file" % (name, n, len(F.fds)), flush=True)


class Timeout(Exception):
    pass


def alarm(signum, frame):
    raise Timeout()


signal.signal(signal.SIGALRM, alarm)
from fdlib import bits
for label, fn in (("left-reduction check", lambda: all(not any(F.implies(X & ~(1 << a), A) for a in bits(X)) for (X, A) in F.fds)),
                  ("minimal keys", lambda: len(minimal_keys(F, R))),
                  ("3NF synthesis", lambda: len(synthesize_3nf(F))),
                  ("enforceability of Sigma+", lambda: enforceable(F)[0])):
    t0 = time.time()
    signal.alarm(cap)
    try:
        res = fn()
        print("  %-26s %8.1f s  -> %s" % (label, time.time() - t0, str(res)[:60]), flush=True)
    except Timeout:
        print("  %-26s exceeds %d s" % (label, cap), flush=True)
    except CapExceeded as e:
        print("  %-26s cap exceeded: %s" % (label, e), flush=True)
    except Exception as e:
        print("  %-26s error after %.1f s: %s" % (label, time.time() - t0, str(e)[:80]), flush=True)
    finally:
        signal.alarm(0)
