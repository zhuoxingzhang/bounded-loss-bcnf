r"""fdlib.py: functional dependencies on attribute sets represented as Python int bitmasks.

This module is the symbolic counterpart of minloss_bruteforce.py, which enumerates closure tables of
size 2^n and is limited to about seven attributes. Here attributes are 0..n-1, an attribute set is an
int bitmask, and an FD is a pair (lhs, rhs) with rhs a single attribute index (atomic form). Schemata
with dozens of attributes and thousands of FDs are fine as long as the number of minimal FDs is.

Contents
  closures            : linear-time attribute closure (Beeri-Bernstein), minimisation of left-hand sides
  minimal keys        : Lucchesi-Osborn enumeration of all minimal keys of (S, F[S])
  atomic cover        : all minimal FDs X -> A of F^+ (minimal keys of F + A -> R, per attribute A)
  criticality         : violators of a schema, critical / uncritical minimal FDs
  enforceability      : Theorem 3.17: the uncritical minimal FDs of E must cover E
  designs             : BCNF design from an enforceable set, enforced FDs, loss, local enforcement, chase
  classical baselines : minimal cover, 3NF synthesis (BCNF whenever possible), BCNF decomposition
  I/O                 : the JSON format of the FD files in data/fds and the Metanome text format
"""
from itertools import combinations
import json, re

# ----------------------------------------------------------------------------- sets

def popcount(x):
    return bin(x).count("1")

def bits(x):
    while x:
        b = x & -x
        yield b.bit_length() - 1
        x ^= b

def mask(it):
    m = 0
    for a in it:
        m |= 1 << a
    return m

def fmt_set(X, names=None):
    return "".join(names[a] if names else chr(65 + a) if a < 26 else "x%d" % a for a in bits(X)) or "{}"

def fmt_fd(f, names=None):
    return "%s->%s" % (fmt_set(f[0], names), fmt_set(1 << f[1], names))

# ----------------------------------------------------------------------------- closures

class FDSet:
    """A list of atomic FDs with an index for linear-time closures."""

    def __init__(self, n, fds):
        self.n = n
        self.fds = [(l, r) for (l, r) in fds if not (l >> r) & 1]  # drop trivial FDs
        self.by_attr = [[] for _ in range(n)]
        self.size = []
        self.empty_lhs = []
        for i, (l, r) in enumerate(self.fds):
            self.size.append(popcount(l))
            if l == 0:
                self.empty_lhs.append(r)
            for a in bits(l):
                self.by_attr[a].append(i)
        self._cache = {}

    def __len__(self):
        return len(self.fds)

    def closure(self, X):
        C = self._cache.get(X)
        if C is not None:
            return C
        cnt = list(self.size)
        C = X
        stack = list(bits(X))
        for r in self.empty_lhs:
            if not (C >> r) & 1:
                C |= 1 << r
                stack.append(r)
        fds, by_attr = self.fds, self.by_attr
        while stack:
            a = stack.pop()
            for i in by_attr[a]:
                cnt[i] -= 1
                if cnt[i] == 0:
                    r = fds[i][1]
                    if not (C >> r) & 1:
                        C |= 1 << r
                        stack.append(r)
        if len(self._cache) < 200000:
            self._cache[X] = C
        return C

    def implies(self, X, A):
        return (self.closure(X) >> A) & 1 == 1

    def closure_without(self, X, disabled, record=None):
        """Closure of X under the FDs whose index is not in `disabled` (no index rebuild).
        If `record` is a list, the indices of the FDs that fired are appended to it."""
        cnt = list(self.size)
        C = X
        stack = list(bits(X))
        fds, by_attr = self.fds, self.by_attr
        for i, (l, r) in enumerate(fds):
            if l == 0 and i not in disabled and not (C >> r) & 1:
                C |= 1 << r
                stack.append(r)
                if record is not None:
                    record.append(i)
        while stack:
            a = stack.pop()
            for i in by_attr[a]:
                cnt[i] -= 1
                if cnt[i] == 0 and i not in disabled:
                    r = fds[i][1]
                    if not (C >> r) & 1:
                        C |= 1 << r
                        stack.append(r)
                        if record is not None:
                            record.append(i)
        return C

    def restrict(self, S):
        """The FDs that lie inside S. For an atomic cover this is a cover of the projection onto S."""
        return FDSet(self.n, [(l, r) for (l, r) in self.fds if (l | (1 << r)) & ~S == 0])

def minimize_lhs(F, X, A):
    """A minimal subset of X that still determines A (greedy, deterministic)."""
    for a in list(bits(X)):
        Y = X & ~(1 << a)
        if F.implies(Y, A):
            X = Y
    return X

def minimize_key(F, X, S):
    """A minimal subset of X whose closure still covers S."""
    for a in list(bits(X)):
        Y = X & ~(1 << a)
        if F.closure(Y) & S == S:
            X = Y
    return X

# ----------------------------------------------------------------------------- minimal keys and atomic cover

class CapExceeded(Exception):
    pass

def minimal_keys(F, S, cap=None):
    """All minimal keys of (S, F[S]) by the Lucchesi-Osborn exchange algorithm.
    F must be a cover of the FDs on S (for S a proper subschema, pass the restriction of an atomic cover)."""
    keys = [minimize_key(F, S, S)]
    i = 0
    while i < len(keys):
        K = keys[i]
        i += 1
        for (Y, B) in F.fds:
            if (K >> B) & 1 and Y & ~S == 0:
                T = Y | (K & ~(1 << B))
                if not any(K2 & ~T == 0 for K2 in keys):
                    keys.append(minimize_key(F, T, S))
                    if cap is not None and len(keys) > cap:
                        raise CapExceeded("more than %d minimal keys" % cap)
    return keys

def minimal_generators(F, A, cap=None):
    """All minimal X with A in closure(X) and A not in X: the minimal keys of F + {A -> R} other
    than {A} (the exchange algorithm needs the FDs A -> b to be complete, so they are really added)."""
    if not any(F.implies(Y, A) and not (Y >> A) & 1 for (Y, B) in F.fds):
        return []
    R = (1 << F.n) - 1
    Fp = FDSet(F.n, F.fds + [(1 << A, b) for b in range(F.n) if b != A])
    return [K for K in minimal_keys(Fp, R, cap) if K != 1 << A]

def atomic_cover(F, cap=None):
    """All minimal FDs (X, A) of F^+, as an FDSet (the atomic cover, Sigma_a in the paper)."""
    out = []
    for A in range(F.n):
        for X in minimal_generators(F, A, cap):
            out.append((X, A))
        if cap is not None and len(out) > cap:
            raise CapExceeded("more than %d minimal FDs" % cap)
    return FDSet(F.n, out)

# ----------------------------------------------------------------------------- criticality and enforceability

def violators(Fa, S):
    """Minimal FDs Y -> B of Fa (an atomic cover of E) with YB inside S and Y not a key of S for E."""
    out = []
    for (Y, B) in Fa.fds:
        if (Y | (1 << B)) & ~S == 0 and Fa.closure(Y) & S != S:
            out.append((Y, B))
    return out

def is_bcnf(Fa, S):
    for (Y, B) in Fa.fds:
        if (Y | (1 << B)) & ~S == 0 and Fa.closure(Y) & S != S:
            return False
    return True

def split_critical(Fa):
    """(uncritical, critical) minimal FDs of the closed set with atomic cover Fa."""
    unc, crit = [], []
    for (X, A) in Fa.fds:
        (unc if is_bcnf(Fa, X | (1 << A)) else crit).append((X, A))
    return unc, crit

def enforceable(Fa):
    """Theorem 3.17: E is enforceable iff its uncritical minimal FDs cover E.
    Returns (bool, U) with U the FDSet of uncritical minimal FDs."""
    unc, crit = split_critical(Fa)
    U = FDSet(Fa.n, unc)
    for (X, A) in crit:
        if not U.implies(X, A):
            return False, U
    return True, U

# ----------------------------------------------------------------------------- designs

def design_from_cover(Fa, U, R=None):
    """A BCNF design for the enforceable set with atomic cover Fa and uncritical cover U.
    Schemata: for every left-hand side X of U, X together with as many of its right-hand sides as keep the
    schema in BCNF; a minimal key of (R, E) if no schema is a superkey; subsumed schemata removed.
    Returns a list of (S, keys)."""
    n = Fa.n
    R = (1 << n) - 1 if R is None else R
    groups = {}
    for (X, A) in U.fds:
        groups.setdefault(X, []).append(A)
    schemata = []
    for X, As in groups.items():
        S = X
        for A in As:
            if is_bcnf(Fa, S | (1 << A)):
                S |= 1 << A
            else:
                schemata.append(X | (1 << A))
        if S != X:
            schemata.append(S)
    if not any(Fa.closure(S) & R == R for S in schemata):
        schemata.append(minimize_key(Fa, R, R))
    schemata = sorted(set(schemata), key=lambda S: (-popcount(S), S))
    kept = []
    for S in schemata:
        if not any(S & ~T == 0 for T in kept):
            kept.append(S)
    design = [(S, minimal_keys(Fa.restrict(S), S)) for S in kept]
    # drop schemata whose key dependencies the other schemata already enforce (smallest first),
    # as long as a superkey schema remains, so that the decomposition stays lossless
    design.sort(key=lambda d: (popcount(d[0]), d[0]))
    i = 0
    while i < len(design):
        others = design[:i] + design[i + 1:]
        if any(Fa.closure(S) & R == R for S, _ in others):
            E_others = key_dependencies(n, others)
            S, keys = design[i]
            if all(E_others.implies(K, b) for K in keys for b in bits(S & ~K)):
                del design[i]
                continue
        i += 1
    design.sort(key=lambda d: (-popcount(d[0]), d[0]))
    return design

def key_dependencies(n, design):
    fds = []
    for S, keys in design:
        for K in keys:
            for b in bits(S & ~K):
                fds.append((K, b))
    return FDSet(n, fds)

def loss_of(Da, E, w=None):
    """Weighted loss of the closed set E (an FDSet cover of it) with respect to the atomic cover Da."""
    tot = 0
    for f in Da.fds:
        if not E.implies(f[0], f[1]):
            tot += 1 if w is None else w[f]
    return tot

def unenforced(Da, E):
    return [f for f in Da.fds if not E.implies(f[0], f[1])]

def is_locally_enforced(design, Ea):
    """Every minimal FD of E inside a schema has a declared key inside its left-hand side."""
    for S, keys in design:
        for (Y, B) in Ea.fds:
            if (Y | (1 << B)) & ~S == 0 and not any(K & ~Y == 0 for K in keys):
                return False
    return True

def chase_lossless(n, schemata, F):
    """Tableau chase: is the decomposition lossless for the FD set F? (validation only; small inputs)"""
    m = len(schemata)
    # cell (i, a) = ('a', a) distinguished if a in schemata[i] else ('b', i, a)
    tab = [[a if (S >> a) & 1 else (i, a) for a in range(n)] for i, S in enumerate(schemata)]
    # union-find over symbols: distinguished symbols are ints, others are tuples
    parent = {}
    def find(x):
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x
    def union(x, y):
        rx, ry = find(x), find(y)
        if rx == ry:
            return False
        # keep distinguished symbols as roots
        if isinstance(rx, tuple) and not isinstance(ry, tuple):
            rx, ry = ry, rx
        parent[ry] = rx
        return True
    changed = True
    while changed:
        changed = False
        for (X, A) in F.fds:
            for i in range(m):
                for j in range(i + 1, m):
                    if all(find(tab[i][a]) == find(tab[j][a]) for a in bits(X)):
                        if union(tab[i][A], tab[j][A]):
                            changed = True
    for i in range(m):
        if all(not isinstance(find(tab[i][a]), tuple) for a in range(n)):
            return True
    return False

def check_bcnf_design(n, design, Da, F=None, chase=False):
    """Soundness and local enforcement of a design; returns (sound, locally_enforced, Ea)."""
    E = key_dependencies(n, design)
    Ea = atomic_cover(E)
    local = is_locally_enforced(design, Ea)
    if chase:
        sound = chase_lossless(n, [S for S, _ in design], E)
    else:
        R = (1 << n) - 1
        sound = any(E.closure(S) == R for S, _ in design)  # dependency-preserving + key => lossless
    return sound, local, Ea

# ----------------------------------------------------------------------------- classical baselines

def minimal_cover(F):
    """A minimal (canonical) cover: atomic right-hand sides, minimal left-hand sides, no redundant FDs."""
    fds = []
    seen = set()
    for (X, A) in F.fds:
        X2 = minimize_lhs(F, X, A)
        if (X2, A) not in seen:
            seen.add((X2, A))
            fds.append((X2, A))
    # remove redundant FDs
    i = 0
    while i < len(fds):
        rest = FDSet(F.n, fds[:i] + fds[i + 1:])
        if rest.implies(fds[i][0], fds[i][1]):
            del fds[i]
        else:
            i += 1
    return FDSet(F.n, fds)

def synthesize_3nf(F, Fa=None):
    """Bernstein's 3NF synthesis with a minimal cover, merging of equivalent left-hand sides, removal of
    subsumed schemata and a key schema if needed. Returns the list of schemata (lossless, dependency preserving)."""
    n = F.n
    R = (1 << n) - 1
    C = minimal_cover(F)
    groups = {}
    for (X, A) in C.fds:
        groups.setdefault(C.closure(X), []).append((X, A))
    schemata = []
    for cl, fds in groups.items():
        S = 0
        for (X, A) in fds:
            S |= X | (1 << A)
        schemata.append(S)
    if not any(C.closure(S) == R for S in schemata):
        schemata.append(minimize_key(C, R, R))
    schemata = sorted(set(schemata), key=lambda S: (-popcount(S), S))
    kept = []
    for S in schemata:
        if not any(S & ~T == 0 for T in kept):
            kept.append(S)
    return kept

def synthesize_3nf_bcnf(F, Fa):
    """A lossless, dependency-preserving 3NF decomposition that is in BCNF whenever possible
    (the guarantee of iConf): the BCNF construction if Sigma^+ is enforceable, else 3NF synthesis."""
    ok, U = enforceable(Fa)
    if ok:
        return [S for S, _ in design_from_cover(Fa, U)], True
    return synthesize_3nf(F, Fa), False

def bcnf_decomposition(Fa, R=None, pick="first"):
    """Classical BCNF decomposition on violating FDs: lossless for Sigma, in BCNF, not necessarily
    dependency preserving. pick: 'first' (document order), 'small' (smallest closure), 'large'."""
    n = Fa.n
    R = (1 << n) - 1 if R is None else R
    todo, done = [R], []
    while todo:
        S = todo.pop()
        V = violators(Fa, S)
        if not V:
            done.append(S)
            continue
        if pick == "small":
            Y, B = min(V, key=lambda f: (popcount(Fa.closure(f[0]) & S), f))
        elif pick == "large":
            Y, B = max(V, key=lambda f: (popcount(Fa.closure(f[0]) & S), -f[0]))
        else:
            Y, B = V[0]
        S1 = Fa.closure(Y) & S
        S2 = S & ~(S1 & ~Y)
        todo.append(S2)
        todo.append(S1)
    return sorted(set(done), key=lambda S: (-popcount(S), S))

def keyed(Fa, schemata):
    """Declare all minimal keys of (S, Sigma[S]) on every schema: the classical key declaration."""
    return [(S, minimal_keys(Fa.restrict(S), S)) for S in schemata]

def nonkey_count(Fa, R=None):
    n = Fa.n
    R = (1 << n) - 1 if R is None else R
    return sum(1 for (X, A) in Fa.fds if Fa.closure(X) & R != R)

# ----------------------------------------------------------------------------- I/O

def load_json(path):
    """{"R": n, "fds": [{"lhs": [...], "rhs": [...]}, ...]} (the FD files in data/fds); returns (n, FDSet)."""
    d = json.load(open(path, encoding="utf-8"))
    n = d["R"]
    fds = []
    for x in d.get("fds", d.get("original", [])):
        L = mask(x["lhs"])
        for r in x["rhs"]:
            fds.append((L, r))
    return n, FDSet(n, fds)

def load_metanome_txt(path):
    """Metanome result format with '# COLUMN' name<TAB>id lines and 'a,b->c' result lines.
    Returns (n, FDSet, names)."""
    names = {}
    fds = []
    section = None
    for line in open(path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            section = line[1:].strip().upper()
            continue
        if section == "COLUMN":
            name, idx = line.rsplit("\t", 1)
            names[int(idx)] = name.split(".", 1)[-1]
        elif section == "RESULTS":
            lhs, rhs = line.split("->")
            L = mask(int(t) - 1 for t in lhs.split(",") if t)
            for t in rhs.split(","):
                fds.append((L, int(t) - 1))
    n = max(names) if names else max(max(bits(l)) if l else 0 for l, r in fds) + 1
    return n, FDSet(n, fds), [names.get(i + 1, "c%d" % (i + 1)) for i in range(n)]

def load_any(path):
    if path.lower().endswith(".json"):
        n, F = load_json(path)
        return n, F, None
    return load_metanome_txt(path)
