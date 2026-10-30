import json,sys,math,statistics,collections
ev=json.load(open(sys.argv[1]))
def wil(k,n,z=1.96):
    if n==0: return (0,0)
    p=k/n; d=1+z*z/n; c=p+z*z/(2*n); r=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)); return ((c-r)/d,(c+r)/d)
def dec(a):
    a=float(a); return 1+(a/100 if a>0 else 100/-a)
print('events',len(ev),'stale',sum(e['stale'] for e in ev),'not stale',sum(not e['stale'] for e in ev))
for app in ('prizepicks','underdog'):
  for kind in ('line','price'):
    E=[e for e in ev if e['app']==app and e['kind']==kind]
    S=[e for e in E if e['stale']]
    R=[e for e in S if e['res'] is not None]
    k=sum(e['res'] for e in R); n=len(R); lo,hi=wil(k,n)
    ca=[e['catch'] for e in S if e['catch'] is not None]
    nocatch=sum(e['catch'] is None for e in S)
    line=f"{app:10} {kind:5} events {len(E):4} stale {len(S):4} ({100*len(S)/max(1,len(E)):.0f}%) graded {n:4} hit {100*k/max(1,n):.1f}% [{100*lo:.1f},{100*hi:.1f}]"
    if ca: line+=f" | catch-up med {statistics.median(ca)/60:.0f}m  p25 {sorted(ca)[len(ca)//4]/60:.0f}m p75 {sorted(ca)[3*len(ca)//4]/60:.0f}m, never {nocatch}"
    if app=='underdog':
        rr=[e for e in R if e['price']]
        if rr:
            roi=sum((dec(e['price'])-1) if e['res'] else -1 for e in rr)/len(rr); line+=f" | ROI@price {100*roi:.1f}% n{len(rr)}"
    print(line)
# split by day
print('--- by window (days since 10-20), stale graded')
days=sorted({e['day'] for e in ev if e['stale']})
for app in ('prizepicks','underdog'):
  for kind in ('line','price'):
    for name,f in (('train',lambda d:d<=days[len(days)//2]),('holdout',lambda d:d>days[len(days)//2])):
        R=[e for e in ev if e['app']==app and e['kind']==kind and e['stale'] and e['res'] is not None and f(e['day'])]
        k=sum(e['res'] for e in R); n=len(R)
        print(app,kind,name,n,f"{100*k/max(1,n):.1f}%")
# by time-to-tip bucket and by magnitude for line moves
print('--- by hours to tip (all apps, stale graded)')
for lo,hi in ((0,1),(1,3),(3,6),(6,12),(12,48)):
    R=[e for e in ev if e['stale'] and e['res'] is not None and lo<=e['hrs']<hi]
    k=sum(e['res'] for e in R); n=len(R); l,h=wil(k,n); print(lo,hi,n,f"{100*k/max(1,n):.1f}% [{100*l:.1f},{100*h:.1f}]")
print('--- prizepicks line moves by size')
for m in (0.5,1.0,1.5):
    R=[e for e in ev if e['app']=='prizepicks' and e['kind']=='line' and e['stale'] and e['res'] is not None and e['mag']>=m]
    k=sum(e['res'] for e in R); n=len(R); l,h=wil(k,n); print('mag>=',m,n,f"{100*k/max(1,n):.1f}% [{100*l:.1f},{100*h:.1f}]")
