import sys, random, time, json, os; sys.path.insert(0, sys.argv[1])
from minloss import *
from multiprocessing import Pool
OUT=sys.argv[2]; SECS=float(sys.argv[3])
BASE=parse("ABCDEF",["DF->C","ACE->D","AE->B","AF->D","BDE->A","DE->F"])[1]

def rand_schema(rng):
    if rng.random()<0.4:   # mutate the weighted counterexample by a 7th attribute G
        N=7; F=list(BASE)
        for _ in range(rng.randint(1,3)):
            L=0
            for _ in range(rng.randint(1,3)): L|=1<<rng.randrange(N)
            a=rng.randrange(N)
            if (L>>6)&1==0 and a!=6: a=6 if rng.random()<0.5 else a
            if not (L>>a)&1: F.append((L,a))
        if rng.random()<0.3 and len(F)>1: F.pop(rng.randrange(len(F)))
        return N,F,"mut"
    N=rng.choice([6,7,7])
    F=[]
    for _ in range(rng.randint(3,8)):
        L=0
        for _ in range(rng.choice([1,2,2,3,3])): L|=1<<rng.randrange(N)
        a=rng.randrange(N)
        if not (L>>a)&1: F.append((L,a))
    return N,F,"rnd"

def work(seed):
    rng=random.Random(seed); t0=time.time(); stats={"tried":0,"lossy":0,"nonplain":0,"skipped":0}; hits=[]
    while time.time()-t0<SECS:
        N,F,kind=rand_schema(rng)
        Sa=minimal_fds(N,table(N,F))
        if not 4<=len(Sa)<=22: continue
        stats["tried"]+=1
        if analyse(N,table(N,Sa))[0]: continue
        stats["lossy"]+=1
        try:
            full,_,_=solve(N,F,mode="full",maxk=4)
            if full is None: stats["skipped"]+=1; continue
            plain,_,_=solve(N,F,mode="plain")
            if plain==full: continue
            stats["nonplain"]+=1
            loc,_,_=solve(N,F,mode="local")
        except RuntimeError:
            stats["skipped"]+=1; continue
        if loc!=full:
            hits.append({"N":N,"F":F,"kind":kind,"full":full,"plain":plain,"local":loc})
    return stats,hits

if __name__=="__main__":
    with Pool(16) as p: res=p.map(work, range(int(time.time()),int(time.time())+16))
    tot={k:sum(r[0][k] for r in res) for k in res[0][0]}
    hits=[h for r in res for h in r[1]]
    json.dump({"stats":tot,"hits":hits},open(OUT,"w"))
    print(tot, "hits:", len(hits))
