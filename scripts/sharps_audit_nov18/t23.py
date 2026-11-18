import json,glob,math,collections,pickle
res=json.load(open('br/pm_record/markets.json'))
rank=json.load(open('/Users/jacobputman/Desktop/Draft Tool/data/pm_wallet_rank.json'))['wallets']
tier={w:v['tier'] for w,v in rank.items()}
def stat(xs):
    n=len(xs)
    if n<2: return (n,0,9)
    m=sum(xs)/n; v=sum((x-m)**2 for x in xs)/(n-1); return (n,m,math.sqrt(v/n))
def fm(a): return f"n={a[0]:>5} {a[1]*100:+6.1f}% (t {a[1]/a[2] if a[2]<9 and a[2]>0 else 0:+.1f})"
sides=[] # sport,cid,mt,oi,px,win,usd_for,usd_against,wallets_for,top tier flags
for sp in ['nba','nfl','cfb','cbb']:
    for f in glob.glob(f'br/pm_holders/{sp}/frozen/*/*.json'):
        d=json.load(open(f))
        by=collections.defaultdict(lambda:[{}, {}])
        for cid,oi,w,sh,usd,*_ in d['h']:
            by[cid][oi][w]=by[cid][oi].get(w,0)+usd
        for cid,(a,b) in by.items():
            m=d['mk'].get(cid); r=res.get(cid)
            if not m or not r or r.get('final') is None: continue
            both=set(a)&set(b)
            for oi,(me,ot) in enumerate([(a,b),(b,a)]):
                px=m['px'][oi]
                if px is None or not(0.05<=px<=0.95): continue
                fin=r['final'][oi]
                if fin not in(0.0,1.0): continue
                um=sum(v for w,v in me.items() if w not in both and v>=250)
                uo=sum(v for w,v in ot.items() if w not in both and v>=250)
                tm=[tier.get(w) for w in me if w not in both and me[w]>=250]
                to=[tier.get(w) for w in ot if w not in both and ot[w]>=250]
                sides.append(dict(sp=sp,cid=cid,mt=m['mt'],px=px,win=fin,um=um,uo=uo,
                    pm=sum(1 for t in tm if t in('proven','probable')),po=sum(1 for t in to if t in('proven','probable')),
                    dm=sum(1 for t in tm if t=='dull'),do=sum(1 for t in to if t=='dull')))
print('side rows',len(sides))
def roi(s): return (1/s['px']-1) if s['win']==1 else -1.0
print('\n-- T0 calibration: price only (mid, no spread), all holders-keyframe markets --')
for sp in ['nba','nfl','cfb','cbb']:
    print(sp,fm(stat([roi(s) for s in sides if s['sp']==sp])))
print('\n-- T2 unbiased all-holder money share on side (>=$250 positions, non-hedged), ROI at cut mid price --')
for sp in ['nba','nfl','cfb','cbb','ALL']:
    for lo,hi in [(0,.2),(.2,.4),(.4,.6),(.6,.8),(.8,1.01)]:
        xs=[roi(s) for s in sides if (sp=='ALL' or s['sp']==sp) and s['um']+s['uo']>=2000 and lo<=s['um']/(s['um']+s['uo'])<hi]
        print(sp,f'share {lo}-{hi}',fm(stat(xs)))
print('\n-- T1 rank tiers (pm_wallet_rank proven/probable) for vs against, mid price --')
for sp in ['nba','nfl','cfb','cbb','ALL']:
    a=[roi(s) for s in sides if (sp=='ALL' or s['sp']==sp) and s['pm']>=1 and s['po']==0]
    b=[roi(s) for s in sides if (sp=='ALL' or s['sp']==sp) and s['po']>=1 and s['pm']==0]
    c=[roi(s) for s in sides if (sp=='ALL' or s['sp']==sp) and s['dm']>=1 and s['do']==0]
    print(sp,'ranked-sharp for,none against',fm(stat(a)),'| ranked-sharp against',fm(stat(b)),'| dull for',fm(stat(c)))
print('\n-- T4 FADE dull-for sides: bet the OTHER outcome at (1-px)+1c ask cushion --')
def fade_roi(s):
    p=min(0.99,(1-s['px'])+0.01); w=1-s['win']
    return (1/p-1) if w==1 else -1.0
for sp in ['nba','nfl','cfb','cbb','ALL']:
    xs=[fade_roi(s) for s in sides if (sp=='ALL' or s['sp']==sp) and s['dm']>=1 and s['do']==0]
    ys=[fade_roi(s) for s in sides if (sp=='ALL' or s['sp']==sp) and s['dm']>=1 and s['do']==0 and s['pm']==0]
    print(sp,'fade dull',fm(stat(xs)),'| no ranked sharp on dull side',fm(stat(ys)))
print('\n-- T5 follow ranked sharps at ask (+1c) where no dull/ranked against --')
def fol(s):
    p=min(0.99,s['px']+0.01); return (1/p-1) if s['win']==1 else -1.0
for sp in ['nba','nfl','cfb','cbb','ALL']:
    xs=[fol(s) for s in sides if (sp=='ALL' or s['sp']==sp) and s['pm']>=1 and s['po']==0]
    print(sp,fm(stat(xs)))
