import itertools, sys
def comps(n,N):
    # все состояния: распределения N фишек по n клеткам
    def rec(i,left):
        if i==n-1: yield (left,); return
        for k in range(left+1):
            for r in rec(i+1,left-k): yield (k,)+r
    return rec(0,N)
def step(c,n):
    out=list(c)
    for i,x in enumerate(c):
        if x>=1:
            out[i]-=1; out[(i+x)%n]+=1
    return tuple(out)
def run(n,N):
    states=list(comps(n,N)); nxt={s:step(s,n) for s in states}
    F=sum(1 for s in states if nxt[s]==s)
    # цикловые состояния и переходный процесс
    color={}; cyc=set(); 
    for s in states:
        path=[]; x=s
        while x not in color and x not in cyc:
            color[x]=1; path.append(x); x=nxt[x]
        if x in color and color[x]==1 and x in path:
            i=path.index(x)
            cyc.update(path[i:])
        for p in path: color[p]=2
    # циклы
    seen=set(); C=0; L=0
    for s in cyc:
        if s in seen: continue
        x=s; ln=0
        while True:
            seen.add(x); x=nxt[x]; ln+=1
            if x==s: break
        C+=1; L=max(L,ln)
    # T: глубина до цикла
    depth={}
    def d(s):
        if s in cyc: return 0
        path=[]; x=s
        while x not in cyc and x not in depth:
            path.append(x); x=nxt[x]
        base=0 if x in cyc else depth[x]
        for k,p in enumerate(reversed(path)): depth[p]=base+k+1
        return depth[s]
    T=max(d(s) for s in states)
    return F,C,L,T,len(states)
for n,N in [(6,6),(7,5),(8,8),(9,6),(10,10),(12,7)]:
    print((n,N), dict(zip("FCLT",run(n,N)[:4])), "состояний", run(n,N)[4], flush=True)
