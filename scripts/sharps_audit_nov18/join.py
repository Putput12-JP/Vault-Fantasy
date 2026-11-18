import pickle,json,glob,math,collections
good,feat=pickle.load(open('wf.pkl','rb'))
idx={(r[0],r[2],r[3]):i for i,r in enumerate(good)}
def fpx(res,p):
    return (1/p-1) if res=='win' else -1.0
def stat(xs):
    n=len(xs)
    if n==0: return (0,0,0)
    m=sum(xs)/n; v=sum((x-m)**2 for x in xs)/max(n-1,1); return (n,m,math.sqrt(v/n))
def fmt(s): return f"n={s[0]:>5} roi={s[1]*100:+6.1f}% se={s[2]*100:4.1f}"
out=[]
for sp in ['nba','nfl','cfb','cbb']:
    for f in glob.glob(f'br/pm_holders/{sp}/frozen/*/*.json') if sp in('nba','nfl') else []:
        d=json.load(open(f))
        for cid,oi,w,sh,usd,fs,fsp,cens,conf in d['h']:
            i=idx.get((w,cid,oi))
            if i is None or sh<=0: continue
            p=usd/sh
            r=good[i]
            out.append((sp,w,r[4],p,r[7],usd,feat[i],r[12],r[5]))
print('joined',len(out))
for sp in ['nba','nfl']:
    o=[x for x in out if x[0]==sp and 0.05<=x[3]<=0.95]
    print(sp,'wallet avg  ',fmt(stat([fpx(x[4],x[2]) for x in o])))
    print(sp,'at cut price',fmt(stat([fpx(x[4],x[3]) for x in o])))
    print(sp,'mean avg',sum(x[2] for x in o)/len(o),'mean cut',sum(x[3] for x in o)/len(o))
    # by size $
    for lo,hi in [(250,1000),(1000,5000),(5000,1e9)]:
        oo=[x for x in o if lo<=x[5]<hi]
        print('  $',lo,hi,'avg',fmt(stat([fpx(x[4],x[2]) for x in oo])),'| cut',fmt(stat([fpx(x[4],x[3]) for x in oo])))
