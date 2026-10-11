"""hardness_check.py: the reduction from Maximum Independent Set to MinLoss with an explicit atomic cover
(Theorem "NP-hardness with explicit atomic cover"), checked with Drop on small graphs.

Graph G = (V, E) with n = |V| and m = |E|.  Attributes P_v, Q_v per vertex and G_e, C_e, D_e^1..D_e^N per edge e = uv.
FDs (the set is its own atomic cover):
  a_v:   P_v -> Q_v                                 vertex FD
  b_e:   Q_u Q_v G_e -> C_e                         edge FD
  s_e^u: P_u G_e -> C_e,  s_e^v: P_v G_e -> C_e     blockers: they make P_u P_v G_e -> C_e non-minimal, so it is not counted
  h_e^i: C_e P_u P_v D_e^i -> G_e, i = 1..N         victims: critical iff some FD X G_e -> C_e with X within P_u P_v is enforced
Claim: for N >= 3, loss(R, Sigma) = 2m + n - alpha(G), where alpha is the size of a maximum independent set.
With N = 2 the loss is 2m, since an edge can keep a blocker and lose its two victims.

usage: python src/hardness_check.py [time_limit] [N] [graphs]      (defaults: 600 s per graph, N = 3, all graphs)
For every graph the script builds the schema, checks that it is its own atomic cover of size n + (3 + N) m, computes the
explicit design for a maximum independent set (closed and enforceable with loss 2m + n - alpha), and runs Drop.
"""
import sys, itertools, time
from fdlib import *
from drop import drop

GRAPHS = {
    "K2": (2, [(0, 1)]),
    "P3": (3, [(0, 1), (1, 2)]),
    "K3": (3, [(0, 1), (1, 2), (0, 2)]),
    "S3": (4, [(0, 1), (0, 2), (0, 3)]),
    "P4": (4, [(0, 1), (1, 2), (2, 3)]),
    "C4": (4, [(0, 1), (1, 2), (2, 3), (3, 0)]),
    "K4": (4, [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]),
    "C5": (5, [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)]),
    "bow": (5, [(0, 1), (1, 2), (0, 2), (2, 3), (3, 4), (2, 4)]),
    "P3+K2": (5, [(0, 1), (1, 2), (3, 4)]),
}

def alpha(nv, edges):
    return max(k for k in range(nv + 1) for S in itertools.combinations(range(nv), k)
               if all(not (u in S and v in S) for u, v in edges))

class Builder:
    def __init__(self):
        self.names, self.idx, self.fds = [], {}, []
    def a(self, name):
        if name not in self.idx:
            self.idx[name] = len(self.names); self.names.append(name)
        return self.idx[name]
    def fd(self, lhs, rhs):
        self.fds.append((mask([self.a(x) for x in lhs]), self.a(rhs)))
    def build(self):
        return len(self.names), FDSet(len(self.names), self.fds), self.names

def schema(nv, edges, N=3):
    b = Builder()
    for v in range(nv):
        b.fd(["P%d" % v], "Q%d" % v)
    for e, (u, v) in enumerate(edges):
        G, C = "G%d" % e, "C%d" % e
        b.fd(["Q%d" % u, "Q%d" % v, G], C)
        b.fd(["P%d" % u, G], C)
        b.fd(["P%d" % v, G], C)
        for i in range(N):
            b.fd([C, "P%d" % u, "P%d" % v, "D%d_%d" % (e, i)], G)
    return b.build()

def explicit(nv, edges, I, n, F, names):
    """the design for an independent set I: drop the blockers and a_v for v not in I; return (loss, closed, enforceable)"""
    Da = atomic_cover(F)
    ix = {nm: i for i, nm in enumerate(names)}
    def fd(l, r): return (mask([ix[x] for x in l]), ix[r])
    Delta = set()
    for v in range(nv):
        if v not in I:
            Delta.add(fd(["P%d" % v], "Q%d" % v))
    for e, (u, v) in enumerate(edges):
        Delta.add(fd(["P%d" % u, "G%d" % e], "C%d" % e))
        Delta.add(fd(["P%d" % v, "G%d" % e], "C%d" % e))
    assert all(f in set(Da.fds) for f in Delta)
    E = atomic_cover(FDSet(n, [f for f in Da.fds if f not in Delta]))
    rederived = [fmt_fd(f, names) for f in Delta if E.implies(*f)]
    ok, _ = enforceable(E)
    return loss_of(Da, E), not rederived, ok

if __name__ == "__main__":
    limit = float(sys.argv[1]) if len(sys.argv) > 1 else 600
    N = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    only = sys.argv[3].split(",") if len(sys.argv) > 3 else None
    allok = True
    for name, (nv, edges) in GRAPHS.items():
        if only and name not in only:
            continue
        n, F, names = schema(nv, edges, N)
        Da = atomic_cover(F)
        m = len(edges)
        al = alpha(nv, edges)
        expected = 2 * m + nv - al if N >= 3 else 2 * m
        assert len(Da) == nv + (3 + N) * m, (len(Da), nv + (3 + N) * m)
        assert set(Da.fds) == set(F.fds), "Sigma is not its own atomic cover"
        I = next(S for k in range(nv, -1, -1) for S in itertools.combinations(range(nv), k)
                 if all(not (u in S and v in S) for u, v in edges))
        el, closed, enf = explicit(nv, edges, set(I), n, F, names)
        t0 = time.time()
        r = drop(n, Da, max_w=4, time_limit=limit)
        good = r.exact and r.loss == expected and closed and enf and (N < 3 or el == expected)
        allok &= good
        print("%s %-6s n=%d m=%d alpha=%d |R|=%2d |Sa|=%3d  expected=%d  explicit: loss=%d closed=%s enforceable=%s  Drop: loss=%s%s lb=%s  %.1fs" % (
            "OK " if good else "BAD", name, nv, m, al, n, len(Da), expected, el, closed, enf,
            r.loss, "" if r.exact else "?", r.lower_bound, time.time() - t0), flush=True)
        if r.delta is not None:
            print("     dropped:", [fmt_fd(f, names) for f in r.delta], " W:", [fmt_fd(f, names) for f in (r.W or [])], flush=True)
    print("ALL OK" if allok else "FAILURES")
