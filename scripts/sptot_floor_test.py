#!/usr/bin/env python3
"""Held-out test of a lower price floor for spread and total rows (docs/sptot-price-floor-prereg.md).
usage: python3 scripts/sptot_floor_test.py --ledger=<dir with v2_watch.json, v2_passed.json from sharp-data> [--tape=data/book_tape] [--out=results.json]"""
import argparse
ap=argparse.ArgumentParser(); ap.add_argument('--ledger',required=True); ap.add_argument('--tape',default='data/book_tape'); ap.add_argument('--out',default='sptot_floor_results.json')
ARGS=ap.parse_args()
import json,glob,bisect,collections,random,datetime as dt
from zoneinfo import ZoneInfo
CT=ZoneInfo('America/Chicago')
rows={}
for fn in ['v2_watch.json','v2_passed.json']:
    for r in json.load(open(''+ARGS.ledger+'/'+fn))['plays'].values():
        if r.get('kind')=='book' and (r.get('game') or {}).get('m') in ('sp','tot'): rows.setdefault(r['id'],r)
tape=collections.defaultdict(list)
for f in glob.glob(ARGS.tape+'/*/*.jsonl'):
    for ln in open(f):
        try: x=json.loads(ln)
        except: continue
        if x.get('book')=='Novig' and x.get('gk') and (x.get('nsp') or x.get('ntot')): tape[x['gk']].append((x['t'],x.get('nsp'),x.get('ntot')))
for k in tape: tape[k].sort(key=lambda z:z[0])
def day(t): return dt.datetime.fromtimestamp(t,CT).date()
TR=(dt.date(2026,10,18),dt.date(2026,11,8)); TE=(dt.date(2026,11,9),dt.date(2026,11,25))
def units(am,st):
    if st=='won': return 100/abs(am) if am<0 else am/100
    if st=='lost': return -1.0
    return 0.0
recs=[]
for r in rows.values():
    st=r.get('status')
    if st not in ('won','lost','push'): continue
    f=r['first']; g=r['game']; fs=r['firstSeen']; d=day(fs)
    win='train' if TR[0]<=d<=TR[1] else 'test' if TE[0]<=d<=TE[1] else None
    if not win: continue
    price=f['price']['p']; am=f['price']['am']
    pin=next((x['p'] for x in f['refs'] if x['n']=='Pinnacle'),None)
    if pin is None: continue
    hrs=(r['start']-fs)/3600; ep=pin/price-1
    p2 = 0.02<=ep<=0.10 and hrs<48
    p1=False
    ts=tape.get(g['gk'],[]); i=bisect.bisect_right([z[0] for z in ts],fs)-1
    if i>=0 and fs-ts[i][0]<=600:
        q=ts[i][1] if g['m']=='sp' else ts[i][2]; ln=g['hline'] if g['m']=='sp' else g['line']
        if q and q[0] is not None and ln is not None and abs(q[0]-ln)<1e-9 and q[2]-q[1]<=0.03+1e-9:
            ph=(q[1]+q[2])/2; pn=ph if g['side'] in('home','over') else 1-ph; en=pn/price-1
            worst=min(ep,en)
            p1 = abs(pin-pn)<=0.04 and 0.02<=worst<=0.10 and hrs<48
    recs.append(dict(win=win,price=price,u=units(am,st),st=st,clv=r.get('clv'),p1=p1,p2=p2,sport=r['sport'],m=g['m']))
def boot(us,n=10000,seed=585):
    if not us: return (None,None)
    rnd=random.Random(seed); k=len(us); out=[]
    for _ in range(n):
        s=[us[rnd.randrange(k)] for _ in range(k)]; out.append(sum(s)/k)
    out.sort(); return out[int(.025*n)],out[int(.975*n)-1]
def summ(rs):
    w=sum(r['st']=='won' for r in rs); l=sum(r['st']=='lost' for r in rs); p=sum(r['st']=='push' for r in rs)
    us=[r['u'] for r in rs]; U=sum(us); n=len(rs); lo,hi=boot(us)
    cl=[r['clv'] for r in rs if r['clv'] is not None]
    return dict(n=n,W=w,L=l,P=p,units=round(U,2),roi=round(U/n*100,1) if n else None,ci=(round(lo*100,1),round(hi*100,1)) if n else None,clv=round(sum(cl)/len(cl)*100,2) if cl else None,nclv=len(cl))
FL=[0.52,0.53,0.54,0.55]
out={}
for pop in ['p1','p2']:
    for win in ['train','test']:
        base=[r for r in recs if r[pop] and r['win']==win]
        for f in FL:
            out[(pop,win,f,'full')]=summ([r for r in base if r['price']>=f])
            if f<0.55: out[(pop,win,f,'band')]=summ([r for r in base if f<=r['price']<0.55])
        out[(pop,win,'all','below52')]=summ([r for r in base if r['price']<0.52])
# choice on train
def pick(pop):
    c=[(out[(pop,'train',f,'band')]['roi'],f) for f in FL[:-1] if out[(pop,'train',f,'band')]['n']>=30]
    return max(c)[1] if c else None
ch=pick('p1'); chpop='p1'
if ch is None: ch=pick('p2'); chpop='p2'
print('chosen on train:',chpop,ch)
for k,v in out.items(): print(k,v)
json.dump({'chosen':[chpop,ch],'rows':{str(k):v for k,v in out.items()}},open(ARGS.out,'w'),indent=1)
