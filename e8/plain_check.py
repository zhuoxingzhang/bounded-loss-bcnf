import itertools,sys
def run(n):
    R=['A','B','E']+[f'C{i}' for i in range(1,n+1)]
    idx={a:i for i,a in enumerate(R)}; N=len(R); full=(1<<N)-1
    def m(*a): 
        x=0
        for s in a: x|=1<<idx[s]
        return x
    Sig=[(m('B'),idx['A'])]
    for i in range(1,n+1):
        Sig+= [(m('B',f'C{i}'),idx['E']),(m('A',f'C{i}','E'),idx['B'])]
    def clo(X,F):
        X0=-1
        while X0!=X:
            X0=X
            for L,a in F:
                if L&X==L: X|=1<<a
        return X
    def minimal(F):
        out=[]
        for X in range(full+1):
            c=clo(X,F)
            for a in range(N):
                if X>>a&1 or not c>>a&1: continue
                if all(not clo(X&~(1<<b),F)>>a&1 for b in range(N) if X>>b&1): out.append((X,a))
        return out
    Sa=minimal(Sig); assert sorted(Sa)==sorted(Sig)
    def bcnf(S,F):
        for X in range(full+1):
            if X&S!=X: continue
            c=clo(X,F)&S
            if c!=X and c!=S: return False
        return True
    best=None
    for k in range(len(Sa)+1):
        for Delta in itertools.combinations(range(len(Sa)),k):
            Psi=[Sa[j] for j in range(len(Sa)) if j not in Delta]
            if any(clo(Sa[j][0],Psi)>>Sa[j][1]&1 for j in Delta): continue  # not plain-closed
            mins=minimal(Psi)
            unc=[(X,a) for X,a in mins if bcnf(X|1<<a,Psi)]
            if all(clo(X,unc)>>a&1 for X,a in mins):
                best=k; break
        if best is not None: break
    print(f'n={n}: |Sigma_a|={len(Sa)}, plain minimum loss={best}')
for n in (2,3,4): run(n)
