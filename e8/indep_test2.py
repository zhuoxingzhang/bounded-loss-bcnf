import sys, random; sys.path.insert(0, sys.argv[1])
from indep import *
from multiprocessing import Pool
def work(seed):
    rng=random.Random(seed); out=[]
    for _ in range(150):
        N=rng.randint(3,6); design=[]
        for _ in range(rng.randint(2,4)):
            S=0
            while bin(S).count("1")<2: S=rng.randrange(1,1<<N)
            attrs=[a for a in range(N) if (S>>a)&1]
            keys=[]
            for _ in range(rng.randint(1,2)):
                K=sum(1<<a for a in rng.sample(attrs, rng.randint(1,len(attrs)-1)))
                if not any(k & K == k for k in keys): keys.append(K)
            design.append((S,keys))
        t_any=lookup_conflict(N,design,"any"); t_first=lookup_conflict(N,design,"first")
        found=False
        for _ in range(600):
            st=random_state(rng,N,design,maxt=3,dom=rng.choice([2,3]))
            if not chase_consistent(N,design,st): found=True; break
        out.append((t_any,t_first,found,N,design))
    return out
if __name__=="__main__":
    with Pool(12) as p: res=[r for rr in p.map(work, range(36)) for r in rr]
    print("designs",len(res))
    print("test says conflict, search found inconsistency:",sum(1 for a,f,x,_,_ in res if a and x))
    print("test says conflict, search found none (search miss?):",sum(1 for a,f,x,_,_ in res if a and not x))
    print("test says independent, search found inconsistency (TEST WRONG):",sum(1 for a,f,x,_,_ in res if not a and x))
    print("test says independent, search found none:",sum(1 for a,f,x,_,_ in res if not a and not x))
    print("all-orders vs canonical-order disagreements:",sum(1 for a,f,x,_,_ in res if a!=f))
    for a,f,x,N,d in res:
        if not a and x: print("example:",N,d); break
