r"""iconf.py: the 3NF synthesis iCONF of Zhang and Link (SIGMOD 2025), ported to Python on top of fdlib.

iconf_decomposition(n, Da) follows iCONF.exe_decomp of the Java implementation with optimization target FDN and
the reduced minimal key/FD cover, the configuration of the experiments of the iCONF paper:

  1. the critical minimal FDs X -> A (those whose schema XA is not in BCNF) are sorted by the number of non-key
     FDs of a reduced minimal key/FD cover of the projection onto XA, largest first, and each is removed from
     the current cover if the rest implies it, else XA becomes a schema;
  2. the other minimal FDs are sorted by the number of minimal keys of XA, largest first, and treated alike;
  3. schemata contained in another schema are removed;
  4. a minimal key of R is added as a schema unless some schema is a superkey.

Both sorts are stable, so ties keep the order of Da. The Java implementation merges right-hand sides in hash
order when it computes the covers that rank the critical FDs, so on ties of that rank the two may treat
critical FDs in a different order; iconf_java(n, Da) runs the Java implementation through iconf/IConfDriver.java
for comparison (iconf/README.md says how to build it).
"""
import os, subprocess, tempfile
from fdlib import FDSet, bits, minimal_keys, is_bcnf

# ----------------------------------------------------------------------------- covers with merged right-hand sides
# an FD is a pair (X, Y) of bitmasks; these follow Utils.compFDCover(..., "reduced minimal") of the Java code

def _closure(fds, X):
    C = X
    changed = True
    while changed:
        changed = False
        for (L, Y) in fds:
            if L & ~C == 0 and Y & ~C:
                C |= Y
                changed = True
    return C

def _combine(fds):
    out = {}
    for (X, Y) in fds:
        out[X] = out.get(X, 0) | Y
    return [(X, Y) for X, Y in out.items()]

def _nonredundant(fds):
    out = list(fds)
    for f in fds:
        rest = [g for g in out if g != f]
        if f[1] & ~_closure(rest, f[0]) == 0:
            out = rest
    return out

def _minimal(fds):
    """Maier's minimum cover: FDs with equivalent left-hand sides are merged where one left-hand side
    directly determines the other"""
    F = list(fds)
    clo = {X: _closure(fds, X) for X, _ in fds}
    groups, seen = [], set()
    for X, _ in fds:
        if X in seen:
            continue
        g = [f for f in fds if clo[f[0]] == clo[X] and f[0] not in seen]
        seen.update(f[0] for f in g)
        groups.append(g)
    for g in groups:
        Fp = [f for f in F if f not in g]
        lhs = {X: (X, Y) for X, Y in g}
        order = [X for X, _ in g]
        for i, X1 in enumerate(order):
            for j, X2 in enumerate(order):
                if i == j or X1 not in lhs or X2 not in lhs:
                    continue
                if X2 & ~_closure(Fp, X1) == 0:
                    f1, f2 = lhs.pop(X1), lhs.pop(X2)
                    F.remove(f1)
                    F.remove(f2)
                    merged = (X2, f1[1] | f2[1])
                    F.append(merged)
                    lhs[X2] = merged
                    break
    return F

def _reduced(fds):
    F = list(fds)
    for i in range(len(F)):                      # left reduction, in place
        X, Y = F[i]
        for a in bits(fds[i][0]):
            if (X >> a) & 1 and Y & ~_closure(F, X & ~(1 << a)) == 0:
                X &= ~(1 << a)
                F[i] = (X, Y)
    F = list(dict.fromkeys(F))
    G = list(F)
    for i in range(len(G)):                      # right reduction, in place
        X, Y = G[i]
        for a in bits(F[i][1]):
            if not (Y >> a) & 1:
                continue
            rest = [g for k, g in enumerate(G) if k != i] + [(X, Y & ~(1 << a))]
            if (_closure(rest, X) >> a) & 1:
                Y &= ~(1 << a)
                G[i] = (X, Y)
    return [f for f in dict.fromkeys(G) if f[1]]

def _reduced_minimal(fds):
    return _combine(_reduced(_minimal(_nonredundant(_combine(fds)))))

def fdn_target(Da, S):
    """the number of non-key FDs of a reduced minimal key/FD cover of the projection of Da onto S"""
    proj = Da.restrict(S)
    cover = _reduced_minimal([(X, 1 << A) for (X, A) in proj.fds])
    keyfds = [(K, S & ~K) for K in minimal_keys(proj, S)]
    rest = list(cover)
    for f in cover:
        rest.remove(f)
        if f[1] & ~_closure(keyfds + rest, f[0]):
            rest.append(f)
    return len(_reduced_minimal(rest))

# ----------------------------------------------------------------------------- iCONF

def iconf_decomposition(n, Da):
    """the schemata (bitmasks) that iCONF returns on the atomic cover Da over n attributes"""
    R = (1 << n) - 1
    fds = Da.fds
    bcnf, target, nkeys = {}, {}, {}
    crit, noncrit = [], []
    for i, (X, A) in enumerate(fds):
        S = X | (1 << A)
        if S not in bcnf:
            bcnf[S] = is_bcnf(Da, S)
        if bcnf[S]:
            noncrit.append(i)
        else:
            crit.append(i)
            if S not in target:
                target[S] = fdn_target(Da, S)
    for i in noncrit:
        S = fds[i][0] | (1 << fds[i][1])
        if S not in nkeys:
            nkeys[S] = len(minimal_keys(Da.restrict(S), S))
    crit.sort(key=lambda i: -target[fds[i][0] | (1 << fds[i][1])])
    noncrit.sort(key=lambda i: -nkeys[fds[i][0] | (1 << fds[i][1])])
    removed, D = set(), []
    for i in crit + noncrit:
        X, A = fds[i]
        removed.add(i)
        if (Da.closure_without(X, removed) >> A) & 1:
            continue
        removed.discard(i)
        S = X | (1 << A)
        if S not in D:
            D.append(S)
    D = [S for k, S in enumerate(D) if not any(k != j and S & ~T == 0 for j, T in enumerate(D))]
    if not any(Da.closure(S) == R for S in D):
        K = R
        for a in range(n):
            if Da.closure(K & ~(1 << a)) == R:
                K &= ~(1 << a)
        D.append(K)
    return D

# ----------------------------------------------------------------------------- the Java implementation, for comparison

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)   # the repository root, which holds data/, results/ and iconf/

def classpath():
    cp = os.environ.get("ICONF_CP")
    if cp:
        return cp
    b = os.path.join(ROOT, "iconf", "build")
    return os.pathsep.join([os.path.join(b, "classes"), os.path.join(b, "fastjson-1.2.79.jar")])

def iconf_java(n, Da, timeout=None, java="java"):
    """the schemata of the Java implementation of iCONF on Da, and its running time in seconds"""
    with tempfile.TemporaryDirectory() as d:
        fin, fout = os.path.join(d, "fds.txt"), os.path.join(d, "out.txt")
        with open(fin, "w") as f:
            for X, A in Da.fds:
                f.write("%s -> %d\n" % (" ".join(str(a) for a in bits(X)), A))
        subprocess.run([java, "-cp", classpath(), "IConfDriver", fin, str(n), fout], check=True, timeout=timeout,
                       stdout=subprocess.DEVNULL)
        dec, t = [], None
        for line in open(fout):
            if line.startswith("# time_ms"):
                t = int(line.split()[2]) / 1000.0
                continue
            S = 0
            for a in line.split():
                S |= 1 << int(a)
            if S:
                dec.append(S)
    return dec, t
