import pickle,math,collections,sys
rows,mk=pickle.load(open('rows.pkl','rb'))
def fp(r):
    avg,res=r[4],r[7]
    if res=='win': return 1/avg-1
    if res=='loss': return -1.0
    return 0.0
good=[r for r in rows if not r[13] and not r[14] and 0.05<=r[4]<=0.95 and r[7] in('win','loss')]
print('usable',len(good),'of',len(rows))
def stat(xs):
    n=len(xs)
    if n==0: return (0,0,0,0)
    m=sum(xs)/n; v=sum((x-m)**2 for x in xs)/max(n-1,1)
    return (n,m,math.sqrt(v/n),sum(1 for x in xs if x>0)/n)
def fmt(s): return f"n={s[0]:>6} roi={s[1]*100:+6.1f}% se={s[2]*100:4.1f} win={s[3]*100:4.1f}%"
# 1 population
for sp in ['nba','nfl','cfb','cbb']:
    for src in ['backfill','forward']:
        xs=[fp(r) for r in good if r[1]==sp and r[15]==src]
        print(sp,src,fmt(stat(xs)))
# walk-forward features
ev=[]
for i,r in enumerate(good):
    ev.append((r[9],0,i))      # settle
    ev.append((r[8]-900,1,i))  # query
ev.sort()
st=collections.defaultdict(lambda:[0,0,0.0,0.0,0.0]) # n,w,fpsum,stake,pnl
feat=[None]*len(good)
for t,k,i in ev:
    r=good[i]; key=(r[0],r[1])
    if k==1:
        s=st[key]; feat[i]=(s[0],s[1],s[2],s[3],s[4])
    else:
        s=st[key]; s[0]+=1; s[1]+=1 if r[7]=='win' else 0; s[2]+=fp(r); s[3]+=r[5]; s[4]+=r[6]
pickle.dump((good,feat),open('wf.pkl','wb'))
def proven_card(f): 
    n,w,fs,stk,pnl=f
    return n>=6 and w/n>=.55 and stk>0 and pnl/stk>.03
print('\n== current card rule "proven" (prior n>=6, win>=55%, $ROI>3%) vs not, forward ==')
for sp in ['nba','nfl','cfb','cbb']:
    a=[fp(r) for r,f in zip(good,feat) if r[1]==sp and proven_card(f)]
    b=[fp(r) for r,f in zip(good,feat) if r[1]==sp and f[0]>=6 and not proven_card(f)]
    c=[fp(r) for r,f in zip(good,feat) if r[1]==sp and f[0]<6]
    print(sp,'proven   ',fmt(stat(a)));print(sp,'not proven',fmt(stat(b)));print(sp,'thin(<6) ',fmt(stat(c)))
print('\n== prior flat-ROI buckets (prior n>=20), forward flat ROI ==')
for sp in ['nba','nfl','cfb','cbb']:
    for lo,hi in [(-9,-.15),(-.15,-.05),(-.05,.0),(0,.05),(.05,.15),(.15,9)]:
        xs=[fp(r) for r,f in zip(good,feat) if r[1]==sp and f[0]>=20 and lo<=f[2]/f[0]<hi]
        print(sp,f'prior [{lo:+.2f},{hi:+.2f})',fmt(stat(xs)))
print('\n== price bucket, all rows ==')
for lo,hi in [(.05,.2),(.2,.35),(.35,.5),(.5,.65),(.65,.8),(.8,.95)]:
    for sp in ['nba','nfl','cfb','cbb']:
        xs=[fp(r) for r in good if r[1]==sp and lo<=r[4]<hi]
        print(sp,f'avg {lo}-{hi}',fmt(stat(xs)))
