"""Summarise build_steam_dk.py output: hit rate, ROI, expected vs actual (z), catch-up time. Usage: analyze_steam_dk.py <events.json>"""
import json,sys,math,statistics
ev=json.load(open(sys.argv[1]))
def wil(k,n,z=1.96):
    if n==0: return (0,0)
    p=k/n; d=1+z*z/n; c=p+z*z/(2*n); r=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)); return ((c-r)/d,(c+r)/d)
def dec(a):
    a=float(a); return 1+(a/100 if a>0 else 100/-a)
def roi(R): return sum((dec(e['px'])-1) if e['res'] else -1 for e in R)/len(R)
def rep(name,R):
    G=[e for e in R if e['res'] is not None]
    if not G: print(f"{name:42} n0"); return
    k=sum(e['res'] for e in G); n=len(G); lo,hi=wil(k,n)
    ec=[e['ev_c'] for e in R if e.get('ev_c') is not None]
    et=[e['ev_t'] for e in R if e.get('ev_t') is not None]
    ca=[e['catch'] for e in R if e['catch'] is not None]
    s=f"{name:42} n {n:4} hit {100*k/n:.1f}% [{100*lo:.1f},{100*hi:.1f}] ROI@DK {100*roi(G):+.1f}%"
    if et: s+=f" | EV vs Pin now {100*statistics.mean(et):+.1f}%"
    if ec: s+=f" | EV vs Pin close {100*statistics.mean(ec):+.1f}% (n{len(ec)})"
    if ca: s+=f" | DK catch-up med {statistics.median(ca)/60:.0f}m, never {sum(e['catch'] is None for e in R)}/{len(R)}"
    print(s)
print('events',len(ev),'price',sum(e['kind']=='price' for e in ev),'line',sum(e['kind']=='line' for e in ev))
# sanity: over/under orientation. hit rate of Over at DK line overall when same line
over=[e for e in ev if e['same'] and e['res'] is not None]
for d in ('Over','Under'):
    R=[e for e in over if e['dir']==d]; print('orientation check',d,len(R),f"hit {100*sum(e['res'] for e in R)/len(R):.1f}%")
P=[e for e in ev if e['kind']=='price' and e['stale']]
L=[e for e in ev if e['kind']=='line' and e['stale']]
rep('PRICE move, DK on Pinnacle line (all)',P)
rep('LINE move, DK still on old line (all)',L)
for th in (0,0.02,0.04,0.06):
    rep(f'PRICE move, EV vs Pin now >= {int(th*100)}%',[e for e in P if e['ev_t'] is not None and e['ev_t']>=th])
rep('PRICE move, EV < 0 (DK already moved)',[e for e in P if e['ev_t'] is not None and e['ev_t']<0])
print('--- split')
days=sorted({e['day'] for e in P}); mid=days[len(days)//2]
for nm,f in (('train',lambda d:d<=mid),('holdout',lambda d:d>mid)):
    rep(f'PRICE EV>=2% {nm}',[e for e in P if e['ev_t'] is not None and e['ev_t']>=0.02 and f(e['day'])])
print('--- by hours to tip, PRICE EV>=2%')
for lo,hi in ((0,1),(1,3),(3,6),(6,48)):
    rep(f'{lo}-{hi}h',[e for e in P if e['ev_t'] is not None and e['ev_t']>=0.02 and lo<=e['hrs']<hi])
print('--- by stat, PRICE EV>=2%')
for st in ('pts','reb','ast','3pm','pra'):
    rep(st,[e for e in P if e['ev_t'] is not None and e['ev_t']>=0.02 and e['stat']==st])
print('--- by move size, PRICE EV>=2%')
for lo,hi in ((0.02,0.03),(0.03,0.05),(0.05,1)):
    rep(f'move {int(lo*100)}-{int(hi*100)}pp',[e for e in P if e['ev_t'] is not None and e['ev_t']>=0.02 and lo<=e['mag']<hi])

print('--- expected vs actual (Pinnacle fair after the move vs the box score)')
def dec2(a):
    a=float(a); return 1+(a/100 if a>0 else 100/-a)
PP=[e for e in ev if e['kind']=='price' and e['stale'] and e['res'] is not None and e['ev_t'] is not None]
def calib(name,R):
    fair=[(e['ev_t']+1)/dec2(e['px']) for e in R]
    k=sum(e['res'] for e in R); n=len(R); mu=sum(fair); var=sum(p*(1-p) for p in fair); z=(k-mu)/math.sqrt(var)
    pl=[(dec2(e['px'])-1) if e['res'] else -1 for e in R]
    print(f"{name:24} n {n:4} expected hit {100*mu/n:.1f}% actual {100*k/n:.1f}% z {z:+.2f} | expected ROI {100*statistics.mean(e['ev_t'] for e in R):+.1f}% actual {100*statistics.mean(pl):+.1f}% +-{100*statistics.stdev(pl)/math.sqrt(n):.1f}")
calib('all stale price',PP)
for lo,hi,nm in ((0.04,9,'EV>=4%'),(0.02,9,'EV>=2%'),(0,0.02,'EV 0-2%'),(-9,0,'EV<0')):
    calib(nm,[e for e in PP if lo<=e['ev_t']<hi])
