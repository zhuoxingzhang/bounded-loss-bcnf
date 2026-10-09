r"""test_examples.py: Drop and Repair on the schemata of the paper, with the losses proved there."""
from fdlib import *
from drop import drop, drop_from_fds
from repair import repair

def parse(n, spec):
    """'DF->C, ACE->D' over attributes A.. -> FDSet"""
    fds = []
    for part in spec.split(","):
        l, r = part.strip().split("->")
        L = mask(ord(c) - 65 for c in l.strip())
        for c in r.strip():
            fds.append((L, ord(c) - 65))
    return FDSet(n, fds)

def show(name, n, spec, expect, w=None, **kw):
    F = parse(n, spec)
    Da = atomic_cover(F)
    r = drop(n, Da, w, max_w=4, time_limit=120, **kw)
    rr = repair(n, F, Da=Da, w=w, max_w=4, time_limit=120)
    names = [chr(65 + i) for i in range(n)]
    ok = "?  " if expect is None else ("OK " if r.loss == expect else "BAD")
    print("%s %-28s lambda=%s (expected %s) exact=%s delta=%s W=%s | repair: mode=%s loss=%s | %.2fs" % (
        ok, name, r.loss, expect, r.exact, [fmt_fd(f, names) for f in r.delta], [fmt_fd(f, names) for f in r.W],
        rr.mode, rr.loss, r.stats["time"]))
    print("     design:", [(fmt_set(S, names), [fmt_set(K, names) for K in keys]) for S, keys in r.design])
    return r

show("running example (C,S,T,Z)", 4, "A->BC, BC->D, D->C", 1)
show("Thm 5.2 plain", 5, "D->C, BE->C, BD->A, ABC->D", 1)
show("Thm 5.2 key-complete", 5, "B->E, CE->A, CE->B, ADE->B, ABD->C", 2)
show("Prop 5.5 first", 5, "B->A, BC->E, BD->E, ACE->B, ADE->B", 1)
show("Prop 5.5 second", 5, "A->D, DE->A, AE->B, BCE->D", 2)
show("Prop 5.7 cover tight", 5, "A->B, A->D, D->A, B->E, E->B, BC->A", 3)
F6 = parse(6, "DF->C, ACE->D, AE->B, AF->D, BDE->A, DE->F")
Da6 = atomic_cover(F6)
names6 = "ABCDEF"
print("Prop 5.6 atomic cover:", [fmt_fd(f, names6) for f in Da6.fds])
show("Prop 5.6 unit", 6, "DF->C, ACE->D, AE->B, AF->D, BDE->A, DE->F", 3)
delta = {parse(6, "AE->B").fds[0], parse(6, "AF->C").fds[0], parse(6, "AF->D").fds[0]}
w = {f: (1 if f in delta else 4) for f in Da6.fds}
r = show("Prop 5.6 weighted", 6, "DF->C, ACE->D, AE->B, AF->D, BDE->A, DE->F", 3, w=w)
print("     weighted delta must be {AE->B, AF->C, AF->D}:", set(r.delta) == delta, " W local?", [fmt_fd(f, names6) for f in r.W])
show("Prop 3.15 gap n=2 (P1,P2)", 6, "A->BC, BC->D, D->C, D->EF", None)
