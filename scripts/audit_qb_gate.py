# Audit: re-score the QB starter gate (docs/leakage-audit-2026-10-06.md finding 1). Run from repo root.
import sys,json,math,statistics as st
sys.path.insert(0,'scripts')
import build_prop_projections as B
seasons=B.load_seasons(2016)
seq={}
for yr,pl in seasons.items(): seq.update(B.player_games(pl,yr))
HP={'pass_att':(6,4,0),'pass_cmp':(6,4,0),'pass_yd':(6,4,6),'pass_td':(9,8,0)}
def series(rows,key): return [B.num(r[1].get(key)) for r in rows]
# priors
def prior(key,gate):
    v=[]
    for k,rows in seq.items():
        if k[1]!='QB': continue
        v+=[x for x,r in zip(series(rows,key),rows) if x is not None and (not gate or (B.num(r[1].get('att')) or 0)>=15)]
    return st.fmean(v)
def prior_eff(gate):
    e=[]
    for k,rows in seq.items():
        if k[1]!='QB': continue
        for r in rows:
            a=B.num(r[1].get('att')); y=B.num(r[1].get('pyds'))
            if a and a>0 and y is not None and (not gate or a>=15): e.append(y/a)
    return st.fmean(e)
def run(mkt,hist_gate,pop):
    hl,kv,ke=HP[mkt]; key={'pass_att':'att','pass_cmp':'cmp','pass_yd':'pyds','pass_td':'ptds'}[mkt]
    out=[]
    for k,rows in seq.items():
        if k[1]!='QB' or k[2]<2018: continue
        for i,(wk,r) in enumerate(rows):
            att=B.num(r.get('att')); act=B.num(r.get(key))
            if att is None or act is None or att<=0: continue   # didn't play
            past=[(B.num(p.get('att')),p) for _,p in rows[:i]]
            gp=[p for a,p in past if a is not None and a>=15]
            hist=gp if hist_gate else [p for a,p in past if a is not None and a>0]
            if len(gp)<B.MIN_PRIOR: continue          # T-legal established-starter filter, same for all variants
            if pop=='gated' and att<15: continue      # current: score only att>=15
            if mkt=='pass_yd':
                vs=[B.num(p['att']) for p in hist if B.num(p.get('att'))]
                es=[B.num(p['pyds'])/B.num(p['att']) for p in hist if B.num(p.get('att')) and B.num(p.get('pyds')) is not None]
                if len(vs)<3: continue
                pr_v=prior('att',hist_gate); pr_e=prior_eff(hist_gate)
                proj=B.project_series(vs,pr_v,hl,kv)*B.project_series(es,pr_e,hl,ke)
            else:
                vals=[B.num(p.get(key)) for p in hist if B.num(p.get(key)) is not None]
                proj=B.project_series(vals,PR[(mkt,hist_gate)],hl,kv)
            out.append((proj,act,att))
    return out
PR={}
for m,key in (('pass_att','att'),('pass_cmp','cmp'),('pass_td','ptds')):
    for g in (True,False): PR[(m,g)]=prior(key,g)
res={}
for m in HP:
    print('\n',m)
    for hg,pop,lab in ((True,'gated','A current (gate hist, score att>=15)'),(True,'all','B gate hist, score ALL starter games'),(False,'all','C no gate, score ALL starter games')):
        o=run(m,hg,pop); rm=math.sqrt(st.fmean([(p-a)**2 for p,a,_ in o])); b=st.fmean([p-a for p,a,_ in o])
        low=sum(1 for *_,t in o if t<15)/len(o)
        print(f'  {lab:46s} n={len(o):5d} rmse={rm:8.3f} bias(proj-act)={b:7.3f} low-att games={low:.3f}')
print('\n--- C (no gate hist) scored on the SAME att>=15 population as A')
for m in HP:
    o=run(m,False,'gated'); print(m,'n',len(o),'rmse',round(math.sqrt(st.fmean([(p-a)**2 for p,a,_ in o])),3))
print('\n--- real lines (bet_results, settled QB props)')
d=json.load(open('data/bet_results.json'))['props']
for m in HP:
    rows=[r for r in d if r['market']==m and r.get('line_close') is not None and r.get('actual') is not None and r['side']=='over']
    if not rows: continue
    pe=[abs(r['proj']-r['actual']) for r in rows if r.get('proj') is not None]; le=[abs(r['line_close']-r['actual']) for r in rows]
    pb=st.fmean([r['proj']-r['actual'] for r in rows if r.get('proj') is not None]); lb=st.fmean([r['line_close']-r['actual'] for r in rows])
    low=sum(1 for r in rows if m in('pass_att',) and r['actual']<15)
    print(m,'n',len(rows),'MAE proj',round(st.fmean(pe),2),'MAE line',round(st.fmean(le),2),'bias proj',round(pb,2),'bias line',round(lb,2),'actual<15att:',low)
