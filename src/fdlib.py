r"""fdlib.py: functional dependencies on attribute sets represented as Python int bitmasks.

This module is the symbolic counterpart of minloss_bruteforce.py, which enumerates closure tables of
size 2^n and is limited to about seven attributes. Here attributes are 0..n-1, an attribute set is an
int bitmask, and an FD is a pair (lhs, rhs) with rhs a single attribute index (atomic form). Schemata
with dozens of attributes and thousands of FDs are fine as long as the number of minimal FDs is.

Contents
  closures            : linear-time attribute closure (Beeri-Bernstein), minimisation of left-hand sides; the
                        closures run in C (closure.c, compiled with gcc on first import) when a compiler is present
                        and there are at most 64 attributes, and in Python otherwise or with FDLIB_PYTHON=1, with
                        equal results
  minimal keys        : Lucchesi-Osborn enumeration of all minimal keys of (S, F[S])
  atomic cover        : all minimal FDs X -> A of F^+ (minimal keys of F + A -> R, per attribute A)
  criticality         : violators of a schema, critical / uncritical minimal FDs
  enforceability      : Theorem 3.17: the uncritical minimal FDs of E must cover E
  designs             : BCNF design from an enforceable set, enforced FDs, loss, local enforcement, chase
  classical baselines : minimal cover, BCNF decomposition (the 3NF syntheses are in iconf.py)
  I/O                 : the JSON format of the FD files in data/fds and the Metanome text format
"""
from itertools import combinations
import json, re, os, sys, time, ctypes, array, subprocess

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

def _compile_msvc(src, out):
    """closure.c as a DLL from the Visual C++ compiler that vswhere finds (Windows)"""
    import tempfile
    vswhere = os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), "Microsoft Visual Studio",
                           "Installer", "vswhere.exe")
    root = subprocess.check_output([vswhere, "-latest", "-products", "*", "-requires",
                                    "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property",
                                    "installationPath"], text=True).strip()
    vcvars = os.path.join(root, "VC", "Auxiliary", "Build", "vcvars64.bat")
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.check_call('call "%s" >nul && cl /nologo /O2 /LD "%s" /Fe"%s" /link /EXPORT:closure_groups '
                              '/EXPORT:closure_without' % (vcvars, src, os.path.join(tmp, "c.dll")), shell=True,
                              cwd=tmp, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.replace(os.path.join(tmp, "c.dll"), out)

def _load_c():
    """the C closures of closure.c, compiled next to it on first use (gcc, or Visual C++ on Windows); None without
    a compiler"""
    if os.environ.get("FDLIB_PYTHON"):
        return None
    here = os.path.dirname(os.path.abspath(__file__))
    win = sys.platform == "win32"
    src, so = os.path.join(here, "closure.c"), os.path.join(here, "_closure.dll" if win else "_closure.so")
    try:
        if not os.path.isfile(so) or os.path.getmtime(so) < os.path.getmtime(src):
            tmp = "%s.%d" % (so, os.getpid())
            if win:
                _compile_msvc(src, tmp)
            else:
                subprocess.check_call(["gcc", "-O3", "-shared", "-fPIC", "-o", tmp, src], stderr=subprocess.DEVNULL)
            os.replace(tmp, so)
        lib = ctypes.CDLL(so)
    except (OSError, subprocess.CalledProcessError):
        return None
    P, I = ctypes.c_void_p, ctypes.c_int
    lib.closure_groups.restype = ctypes.c_uint64
    lib.closure_groups.argtypes = [P, P, I, ctypes.c_uint64]
    lib.closure_without.restype = ctypes.c_uint64
    lib.closure_without.argtypes = [I, I, P, P, P, P, P, P, I, P, ctypes.c_uint64, P, P, P, P]
    return lib

_C = _load_c()

class FDSet:
    """A list of atomic FDs with an index for linear-time closures."""

    def __init__(self, n, fds):
        self.n = n
        self.fds = [(l, r) for (l, r) in fds if not (l >> r) & 1]  # drop trivial FDs
        self._cache = {}
        self._groups = self._cw = None
        self._c = _C is not None and n <= 64   # the C routines hold attribute sets in 64 bits
        if not self._c:
            self._index()

    def _index(self):
        self.by_attr = [[] for _ in range(self.n)]
        self.size = []
        self.empty_lhs = []
        for i, (l, r) in enumerate(self.fds):
            self.size.append(popcount(l))
            if l == 0:
                self.empty_lhs.append(r)
            for a in bits(l):
                self.by_attr[a].append(i)

    def __len__(self):
        return len(self.fds)

    def closure(self, X):
        C = self._cache.get(X)
        if C is not None:
            return C
        if self._c:
            g = self._groups
            if g is None:
                g = self._groups = self._build_groups()
            C = _C.closure_groups(g[2], g[3], g[4], X)
        else:
            C = self._closure_py(X)
        if len(self._cache) < 200000:
            self._cache[X] = C
        return C

    def _build_groups(self):
        g = {}
        for l, r in self.fds:
            g[l] = g.get(l, 0) | (1 << r)
        order = sorted(g, key=popcount)
        L, R = array.array("Q", order), array.array("Q", [g[l] for l in order])
        return (L, R, L.buffer_info()[0], R.buffer_info()[0], len(L))

    def _closure_py(self, X):
        if not hasattr(self, "size"):
            self._index()
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
        return C

    def implies(self, X, A):
        return (self.closure(X) >> A) & 1 == 1

    def closure_without(self, X, disabled, record=None):
        """Closure of X under the FDs whose index is not in `disabled` (no index rebuild).
        If `record` is a list, the indices of the FDs that fired are appended to it."""
        if not self._c:
            return self._closure_without_py(X, disabled, record)
        c = self._cw
        if c is None:
            c = self._cw = self._build_cw()
        dis = c["dis"]
        for i in disabled:
            dis[i] = 1
        C = _C.closure_without(self.n, len(self.fds), *c["args"], X, *c["scratch"])
        for i in disabled:
            dis[i] = 0
        if record is not None:
            record.extend(c["rec"][:c["nrec"][0]])
        return C

    def nonredundant(self, order=None):
        """the indices of a nonredundant subset of the FDs: every FD, in the given order of indices, is dropped if
        the FDs not dropped so far imply it"""
        order = range(len(self.fds)) if order is None else order
        removed = set()
        if not self._c:
            for i in order:
                removed.add(i)
                X, A = self.fds[i]
                if not (self._closure_without_py(X, removed) >> A) & 1:
                    removed.discard(i)
        else:
            c = self._cw
            if c is None:
                c = self._cw = self._build_cw()
            dis = c["dis"]
            for i in order:
                dis[i] = 1
                X, A = self.fds[i]
                if (_C.closure_without(self.n, len(self.fds), *c["args"], X, *c["scratch"]) >> A) & 1:
                    removed.add(i)
                else:
                    dis[i] = 0
            for i in removed:
                dis[i] = 0
        return [i for i in range(len(self.fds)) if i not in removed]

    def classes(self):
        """the number of equivalence classes of left-hand sides (X ~ Y iff X+ = Y+) in a nonredundant subset of the
        FDs; all nonredundant covers of a closed set have the same number (Maier 1980), a lower bound on the schemata
        of every key design that enforces it, since the keys of a schema have the same closure"""
        return len(set(self.closure(self.fds[i][0]) for i in self.nonredundant()))

    def _build_cw(self):
        """the arrays of the C routine closure_without: FD index by attribute in increasing order, as in _index"""
        m, n = len(self.fds), self.n
        by_attr = [[] for _ in range(n)]
        empty = []
        for i, (l, r) in enumerate(self.fds):
            if l == 0:
                empty.append(i)
            for a in bits(l):
                by_attr[a].append(i)
        start = [0]
        for a in range(n):
            start.append(start[-1] + len(by_attr[a]))
        c = {"lhs": array.array("Q", [l for l, r in self.fds] or [0]),
             "rhs": array.array("i", [r for l, r in self.fds] or [0]),
             "size": array.array("i", [popcount(l) for l, r in self.fds] or [0]),
             "start": array.array("i", start), "idx": array.array("i", [i for a in range(n) for i in by_attr[a]] or [0]),
             "empty": array.array("i", empty or [0]), "dis": bytearray(max(m, 1)),
             "cnt": array.array("i", [0] * max(m, 1)), "stack": array.array("i", [0] * max(n, 1)),
             "rec": array.array("i", [0] * max(n, 1)), "nrec": array.array("i", [0])}
        c["dis_c"] = (ctypes.c_uint8 * len(c["dis"])).from_buffer(c["dis"])
        ptr = lambda k: c[k].buffer_info()[0]
        c["args"] = (ptr("lhs"), ptr("rhs"), ptr("size"), ptr("start"), ptr("idx"), ptr("empty"), len(empty),
                     ctypes.addressof(c["dis_c"]))
        c["scratch"] = (ptr("cnt"), ptr("stack"), ptr("rec"), ptr("nrec"))
        return c

    def _closure_without_py(self, X, disabled, record=None):
        if not hasattr(self, "size"):
            self._index()
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

class DeadlineExceeded(Exception):
    """raised by minimal_keys, minimal_generators and atomic_cover once the time is past their deadline"""

def minimal_keys(F, S, cap=None, deadline=None):
    """All minimal keys of (S, F[S]) by the Lucchesi-Osborn exchange algorithm.
    F must be a cover of the FDs on S (for S a proper subschema, pass the restriction of an atomic cover)."""
    keys = [minimize_key(F, S, S)]
    i = 0
    while i < len(keys):
        if deadline is not None and time.time() > deadline:
            raise DeadlineExceeded("minimal keys past the deadline")
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

def minimal_generators(F, A, cap=None, deadline=None):
    """All minimal X with A in closure(X) and A not in X: the minimal keys of F + {A -> R} other
    than {A} (the exchange algorithm needs the FDs A -> b to be complete, so they are really added)."""
    if not any(F.implies(Y, A) and not (Y >> A) & 1 for (Y, B) in F.fds):
        return []
    R = (1 << F.n) - 1
    Fp = FDSet(F.n, F.fds + [(1 << A, b) for b in range(F.n) if b != A])
    return [K for K in minimal_keys(Fp, R, cap, deadline) if K != 1 << A]

def atomic_cover(F, cap=None, deadline=None):
    """All minimal FDs (X, A) of F^+, as an FDSet (the atomic cover, Sigma_a in the paper); past the deadline (a
    time.time() value), DeadlineExceeded"""
    out = []
    for A in range(F.n):
        for X in minimal_generators(F, A, cap, deadline):
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
    """A BCNF design for the enforceable set E with atomic cover Fa and uncritical cover U, the one with fewer
    schemata of two constructions that enforce E alike (so the loss is the same):
      by left-hand side: for every left-hand side X of U, X together with as many of its right-hand sides as keep
        the schema in BCNF, and XA for each of the others;
      by class: a nonredundant subset of U (larger left-hand sides dropped first), grouped by the closure of the
        left-hand side, and the schemata XA of a group merged first-fit while the union stays in BCNF (only schemata
        whose keys have the same closure can share a BCNF schema);
    then a minimal key of (R, E) if no schema is a superkey, subsumed schemata removed, and schemata removed whose key
    dependencies the others imply. Returns a list of (S, keys)."""
    n = Fa.n
    R = (1 << n) - 1 if R is None else R
    a = _design_schemata(Fa, _schemata_by_lhs(Fa, U), R)
    b = _design_schemata(Fa, _schemata_by_class(Fa, U), R)
    return b if len(b) < len(a) else a

def _schemata_by_lhs(Fa, U):
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
    return schemata

def _schemata_by_class(Fa, U):
    order = sorted(range(len(U.fds)), key=lambda i: (-popcount(U.fds[i][0]), U.fds[i]))
    classes = {}
    for i in U.nonredundant(order):
        X, A = U.fds[i]
        classes.setdefault(Fa.closure(X), []).append((X, A))
    schemata = []
    for fs in classes.values():
        parts = []
        for X, A in sorted(fs, key=lambda f: (popcount(f[0]), f)):
            S = X | (1 << A)
            for j, T in enumerate(parts):
                if S & ~T == 0 or is_bcnf(Fa, T | S):
                    parts[j] = T | S
                    break
            else:
                parts.append(S)
        schemata += parts
    return schemata

def _design_schemata(Fa, schemata, R):
    n = Fa.n
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
    kd, of = [], []
    for S, keys in design:
        of.append([])
        for K in keys:
            for b in bits(S & ~K):
                of[-1].append(len(kd))
                kd.append((K, b))
    H = FDSet(n, kd)
    superkey = [Fa.closure(S) & R == R for S, _ in design]
    supers = sum(superkey)
    dead, deleted = set(), set()
    for j in range(len(design)):
        if supers - superkey[j] == 0:
            continue
        dis = dead | set(of[j])
        if all((H.closure_without(kd[i][0], dis) >> kd[i][1]) & 1 for i in of[j]):
            deleted.add(j)
            dead |= set(of[j])
            supers -= superkey[j]
    design = [d for j, d in enumerate(design) if j not in deleted]
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

def _complete_bcnf(Fa, done, todo):
    """Finish a run of bcnf_decomposition(pick='first') from the state (done, todo)."""
    done, todo = list(done), list(todo)
    while todo:
        S = todo.pop()
        V = violators(Fa, S)
        if not V:
            done.append(S)
            continue
        Y = V[0][0]
        S1 = Fa.closure(Y) & S
        todo.append(S & ~(S1 & ~Y))
        todo.append(S1)
    return sorted(set(done), key=lambda S: (-popcount(S), S))

def greedy_bcnf_decomposition(Fa, R=None, time_limit=None, attribute_splits=True):
    """BCNF decomposition on violating FDs that chooses, for every schema S it splits, the split whose completion
    by the classical algorithm (bcnf_decomposition with pick='first') leaves the fewest minimal FDs unenforced by
    the minimal keys of the resulting schemata. The candidates are the classical splits into Y+ & S and
    S - (Y+ & S - Y) for the left-hand side Y of every violating FD Y -> B and, with attribute_splits, the splits
    into YB and S - B. Ties go to the classical choice, which is always examined first, so the result never
    loses more minimal FDs than the classical decomposition, also when the time limit cuts the search (from then
    on the classical choice is taken, which completes the best decomposition found). Returns (schemata, stats)."""
    import time
    n = Fa.n
    R = (1 << n) - 1 if R is None else R
    t0 = time.time()
    keys_of = {}

    def loss(schemata):
        for S in schemata:
            if S not in keys_of:
                keys_of[S] = minimal_keys(Fa.restrict(S), S)
        return loss_of(Fa, key_dependencies(n, [(S, keys_of[S]) for S in schemata]))

    stats = {"steps": 0, "choices": 0, "rollouts": 0, "deviations": 0, "timed_out": False}
    todo, done = [R], []
    while todo:
        S = todo.pop()
        V = violators(Fa, S)
        if not V:
            done.append(S)
            continue
        splits = []
        for (Y, B) in V:
            S1 = Fa.closure(Y) & S
            for sp in [(S1, S & ~(S1 & ~Y))] + ([(Y | (1 << B), S & ~(1 << B))] if attribute_splits else []):
                if sp not in splits:
                    splits.append(sp)
        choice = splits[0]
        if len(splits) > 1 and not stats["timed_out"]:
            stats["choices"] += 1
            best = None
            for S1, S2 in splits:
                if time_limit is not None and time.time() - t0 > time_limit:
                    stats["timed_out"] = True
                    break
                l = loss(_complete_bcnf(Fa, done, todo + [S2, S1]))
                stats["rollouts"] += 1
                if best is None or l < best:
                    best, choice = l, (S1, S2)
            if choice != splits[0]:
                stats["deviations"] += 1
        stats["steps"] += 1
        todo.append(choice[1])
        todo.append(choice[0])
    stats["time"] = time.time() - t0
    return sorted(set(done), key=lambda S: (-popcount(S), S)), stats

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
