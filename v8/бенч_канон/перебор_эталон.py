import itertools, json, sys
def comps(N,n):
    # all compositions of N into n nonneg parts
    if n==1: yield (N,); return
    for i in range(N+1):
        for rest in comps(N-i,n-1): yield (i,)+rest
def step(s,n):
    t=list(s)
    for i,c in enumerate(s):
        if c>=1:
            t[i]-=1; t[(i+c)%n]+=1
    return tuple(t)
def analyze(n,N):
    states=list(comps(N,n)); nxt={s:step(s,n) for s in states}
    color={}; cyc=[]; trans={}
    for s in states:
        path=[]; x=s
        while x not in color:
            color[x]=1; path.append(x); x=nxt[x]
        if color[x]==1:  # new cycle
            i=path.index(x); cycle=path[i:]; cyc.append(cycle)
            for y in cycle: color[y]=2; trans[y]=0
            path=path[:i]
        for y in reversed(path):
            color[y]=2; trans[y]=trans[nxt[y]]+1
    F=sum(1 for c in cyc if len(c)==1)
    return dict(n=n,N=N,states=len(states),F=F,C=len(cyc),L=max(len(c) for c in cyc),T=max(trans.values()))
res=[analyze(n,N) for n,N in [(6,6),(7,5),(8,8),(9,6),(10,10),(12,7)]]
json.dump(res,open("truth.json","w"))
for r in res: print(r)
# invariant check: sum i*c_i mod n changes by N each step
import random
bad=0
for n,N in [(7,5),(8,8),(6,6)]:
    for s in list(comps(N,n))[:2000]:
        t=step(s,n)
        if (sum(i*c for i,c in enumerate(t))-sum(i*c for i,c in enumerate(s))-N)%n: bad+=1
print("invariant violations:",bad)
# small tables for n=3,4
for n,N in [(3,3),(3,4),(4,4),(4,5),(5,5)]: print(analyze(n,N))
