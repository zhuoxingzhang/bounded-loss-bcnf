"""Majster-Cederbaum's acyclicity test on the FD sets of the experiments.

The graph of a canonical cover has the FDs as nodes and an edge from X -> A to Y -> B whenever A is in Y.
If the graph is acyclic, a lossless, dependency-preserving BCNF decomposition exists, so the loss is zero.
Usage: python3 acyclic.py [names...]
"""
import sys
from fdlib import FDSet, load_any, minimal_cover, bits
from experiments import SETS


def acyclic(n, F):
    cover = minimal_cover(F).fds
    by_rhs = {}
    for (X, A) in cover:
        by_rhs.setdefault(A, []).append((X, A))
    # edges from f = (X, A) to every g = (Y, B) with A in Y
    index = {f: i for i, f in enumerate(cover)}
    succ = [[] for _ in cover]
    for j, (Y, B) in enumerate(cover):
        for A in bits(Y):
            for f in by_rhs.get(A, ()):
                succ[index[f]].append(j)
    # Kahn's algorithm
    indeg = [0] * len(cover)
    for i in range(len(cover)):
        for j in succ[i]:
            indeg[j] += 1
    stack = [i for i in range(len(cover)) if indeg[i] == 0]
    seen = 0
    while stack:
        i = stack.pop()
        seen += 1
        for j in succ[i]:
            indeg[j] -= 1
            if indeg[j] == 0:
                stack.append(j)
    return seen == len(cover), len(cover)


if __name__ == "__main__":
    want = set(sys.argv[1:])
    for name, path in SETS:
        if want and name not in want:
            continue
        n, F, names = load_any(path)
        ok, m = acyclic(n, F)
        print("%-22s cover %6d  %s" % (name, m, "acyclic" if ok else "cyclic"), flush=True)
