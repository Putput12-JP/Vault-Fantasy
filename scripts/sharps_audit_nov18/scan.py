import pickle,math,collections,time
good,feat=pickle.load(open('wf.pkl','rb'))
def fp(r):
    return (1/r[4]-1) if r[7]=='win' else -1.0
SPLIT=1772323200 # 2026-03-01
# per cid consensus: count of "skilled" (prior n>=15, prior flatROI>0.03) wallets per side, and total tracked $ per side
side=collections.defaultdict(lambda:[0,0,0.0,0.0,0,0]) # sk0,sk1,usd0,usd1,lo0,lo1 (losers prior ROI<-0.05,n>=15)
for r,f in zip(good,feat):
    s=side[r[2]]
    sk = f[0]>=15 and f[2]/f[0]>0.03
    lo = f[0]>=15 and f[2]/f[0]<-0.05
    s[r[3]]+= 1 if sk else 0
    s[2+r[3]]+= r[5]
    s[4+r[3]]+= 1 if lo else 0
recs=[]
for r,f in zip(good,feat):
    n,w,fs,stk,pnl=f
    s=side[r[2]]; o=1-r[3]
    mean_stk=(stk/n) if n>=5 else None
    press=(r[5]/mean_stk) if mean_stk else None
    lead=(r[8]-r[10])/3600
    lag=(r[8]-r[11])/3600
    recs.append(dict(sp=r[1],mt=r[12],train=r[8]<SPLIT,fp=fp(r),price=r[4],n=n,proi=(fs/n if n>=15 else None),
        press=press,lead=lead,lag=lag,usd=r[5],skf=s[r[3]],ska=s[o],lof=s[4+r[3]],loa=s[4+o],
        shareusd=s[2+r[3]]/max(s[2]+s[3],1),exited=r[17]>0,post=r[18]>0))
pickle.dump(recs,open('recs.pkl','wb'))
def stat(xs):
    n=len(xs)
    if n<2: return (n,0,9)
    m=sum(xs)/n; v=sum((x-m)**2 for x in xs)/(n-1); return (n,m,math.sqrt(v/n))
def row(name,pred):
    out=[]
    for sp in ['nba','nfl','cfb','cbb']:
        a=stat([x['fp'] for x in recs if x['sp']==sp and x['train'] and pred(x)])
        b=stat([x['fp'] for x in recs if x['sp']==sp and not x['train'] and pred(x)])
        out.append(f"{sp}: tr {a[0]:>6} {a[1]*100:+5.1f}%({a[1]/a[2] if a[2] else 0:+.1f}t) te {b[0]:>5} {b[1]*100:+5.1f}%({b[1]/b[2] if b[2] else 0:+.1f}t)")
    print(f"{name:34s} | "+" | ".join(out))
print('train: before 2026-03-01; test: after. t = roi/se')
row('all',lambda x:True)
for lo,hi in [(0,.25),(.25,.5),(.5,1),(1,2),(2,5),(5,1e9)]:
    row(f'press {lo}-{hi}',lambda x,lo=lo,hi=hi:x['press'] is not None and lo<=x['press']<hi)
for lo,hi in [(0,1),(1,6),(6,24),(24,72),(72,1e9)]:
    row(f'lead h {lo}-{hi}',lambda x,lo=lo,hi=hi:lo<=x['lead']<hi)
for lo,hi in [(0,.5),(.5,2),(2,6),(6,24),(24,1e9)]:
    row(f'lastbuy lag h {lo}-{hi}',lambda x,lo=lo,hi=hi:lo<=x['lag']<hi)
for lo,hi in [(0,250),(250,1000),(1000,5000),(5000,20000),(20000,1e12)]:
    row(f'stake ${lo}-{hi}',lambda x,lo=lo,hi=hi:lo<=x['usd']<hi)
row('skilled for, none against',lambda x:x['skf']>=1 and x['ska']==0)
row('skilled for>=2, none against',lambda x:x['skf']>=2 and x['ska']==0)
row('skilled against>=1, none for',lambda x:x['ska']>=1 and x['skf']==0)
row('loser for>=1, no loser against',lambda x:x['lof']>=1 and x['loa']==0)
row('loser for>=2 (FADE side = their)',lambda x:x['lof']>=2 and x['loa']==0)
row('tracked $ share >=70% on side',lambda x:x['shareusd']>=.7)
row('tracked $ share <=30% on side',lambda x:x['shareusd']<=.3)
