import pickle,math,collections,datetime
good,feat=pickle.load(open('wf.pkl','rb'))
fw=[(r,f) for r,f in zip(good,feat) if r[15]=='forward']
ts=[r[8] for r,f in fw]; print('forward rows',len(fw),datetime.datetime.fromtimestamp(min(ts)),datetime.datetime.fromtimestamp(max(ts)))
def fp(r): return (1/r[4]-1) if r[7]=='win' else -1.0
def stat(xs):
    n=len(xs)
    if n<2: return (n,0,9)
    m=sum(xs)/n; v=sum((x-m)**2 for x in xs)/(n-1); return (n,m,math.sqrt(v/n))
# consensus from forward rows only
side=collections.defaultdict(lambda:[0,0,0.0,0.0,0,0,0,0])
for r,f in fw:
    s=side[r[2]]; k=r[3]
    s[k]+=1; s[2+k]+=r[5]
    if f[0]>=15 and f[2]/f[0]>0.03: s[4+k]+=1
    if f[0]>=15 and f[2]/f[0]<-0.05: s[6+k]+=1
def rep(name,pred):
    parts=[]
    for sp in ['nba','nfl','cfb','cbb','ALL']:
        xs=[fp(r) for r,f in fw if (sp=='ALL' or r[1]==sp) and pred(r,f,side[r[2]])]
        a=stat(xs); parts.append(f"{sp}: n={a[0]:>5} {a[1]*100:+5.1f}% ({a[1]/a[2] if a[2] and a[2]<9 else 0:+.1f}t)")
    print(f"{name:32s}| "+" | ".join(parts))
rep('all forward rows',lambda r,f,s:True)
rep('proven (card rule prior)',lambda r,f,s:f[0]>=6 and f[1]/f[0]>=.55 and f[3]>0 and f[4]/f[3]>.03)
rep('share>=70% tracked $ on side',lambda r,f,s:s[2+r[3]]/max(s[2]+s[3],1)>=.7)
rep('share<=30%',lambda r,f,s:s[2+r[3]]/max(s[2]+s[3],1)<=.3)
rep('skilled for, none against',lambda r,f,s:s[4+r[3]]>=1 and s[4+1-r[3]]==0)
rep('loser for, none against',lambda r,f,s:s[6+r[3]]>=1 and s[6+1-r[3]]==0)
