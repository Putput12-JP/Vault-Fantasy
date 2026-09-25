#!/usr/bin/env python3
# Backtest: history-length (games-of-history) logit shift on prop P(over).
# Nested walk-forward: shifts fit on holdout seasons < T, scored on T (2022-2025).
# Usage: python3 scripts/backtest_history_shift.py rec,rush_att,pass_att out.json [--publish]
#   --publish also fits the shifts on EVERY holdout season (2019..latest) and
#   writes data/prop_history_shift.json, which settle_bets.py reads to log a
#   SHADOW p_hist beside p_model. Shadow only: nothing on the board reads it.
#   Refit once a season (after the new nflverse season lands).
import importlib.util, sys, collections, math, json, os
ROOT="/Users/jacobputman/Desktop/Draft Tool"
spec=importlib.util.spec_from_file_location("bt", ROOT+"/scripts/backtest_prop_model.py")
bt=importlib.util.module_from_spec(spec); spec.loader.exec_module(bt)
B=bt.B; CUR=[None]; SEAS=collections.defaultdict(list)
orig_pf=B.prob_fn_for
def pf_wrap(params):
    f=orig_pf(params); tag=CUR[0]
    def g(proj,line):
        SEAS[tag[0]].append(tag[1]); return f(proj,line)
    return g
B.prob_fn_for=pf_wrap
of=bt.fit_market
def fm(mkt,spec_,train_seq,priors):
    T=max(k[2] for k in train_seq)+1 if train_seq else None
    CUR[0]=(mkt,'fit'); p=of(mkt,spec_,train_seq,priors); CUR[0]=(mkt,T); return p
bt.fit_market=fm
lg=lambda p: math.log(p/(1-p)); sg=lambda x: 1/(1+math.exp(-x))
BINS=[(0,8),(9,14),(15,20),(21,10**6)]
binof=lambda g: next(i for i,(a,b) in enumerate(BINS) if a<=g<=b)
def fit_b(rows):
    if len(rows)<300: return 0.0
    ll=lambda b: sum(-(h*math.log(sg(lg(p)+b))+(1-h)*math.log(1-sg(lg(p)+b))) for p,h in rows)/len(rows)
    lo,hi=-1.0,1.0
    for _ in range(40):
        m1,m2=lo+(hi-lo)/3,hi-(hi-lo)/3
        (hi:=m2) if ll(m1)<ll(m2) else (lo:=m1)
    return (lo+hi)/2
mk=sys.argv[1].split(',')
pooled,graded=bt.holdout(mk,2016,2019,use_calib=True)
out={}
for m in mk:
    tags=[t for t in SEAS[m] if t!='fit']
    rows=[(T,g,p,h) for T,(p,g,h) in zip(tags,graded[m])]
    assert len(tags)==len(graded[m]), (m,len(tags),len(graded[m]))
    base=[];fix=[];shifts={}
    for T in range(2022,2026):
        train=[r for r in rows if r[0]<T]; test=[r for r in rows if r[0]==T]
        bs=[fit_b([(p,h) for _,g,p,h in train if binof(g)==i]) for i in range(len(BINS))]
        shifts[T]=[round(b,3) for b in bs]
        for _,g,p,h in test:
            base.append((g,p,h)); q=min(max(sg(lg(p)+bs[binof(g)]),0.01),0.99); fix.append((g,q,h))
    def summ(R):
        n=len(R); ll=sum(-(h*math.log(p)+(1-h)*math.log(1-p)) for _,p,h in R)/n
        o=[(p,h) for _,p,h in R if p>0.5]; u=[(1-p,1-h) for _,p,h in R if p<0.5]
        gap=lambda X:(sum(h for _,h in X)-sum(p for p,_ in X))/len(X) if X else float('nan')
        fav=[(max(p,1-p), h if p>0.5 else 1-h) for _,p,h in R if abs(p-.5)>=0.05]
        fo=[x for x,(_,p,_) in zip(fav,[r for r in R if abs(r[1]-.5)>=0.05]) if p>0.5]
        fu=[x for x,(_,p,_) in zip(fav,[r for r in R if abs(r[1]-.5)>=0.05]) if p<0.5]
        hr=lambda X:(sum(h for _,h in X)/len(X), len(X)) if X else (float('nan'),0)
        return {"ll":round(ll,4),"over_gap":round(gap(o),3),"under_gap":round(gap(u),3),
                "fav55_over_hit_n":[round(hr(fo)[0],3),hr(fo)[1]],"fav55_under_hit_n":[round(hr(fu)[0],3),hr(fu)[1]]}
    out[m]={"shifts_by_season(bins 0-8,9-14,15-20,21+)":shifts,"base":summ(base),"fix":summ(fix)}
    print(m, json.dumps(out[m]))
json.dump(out,open(sys.argv[2],'w'),indent=1)
if '--publish' in sys.argv:
    import datetime
    # Markets where the nested walk-forward improved OOS log-loss. rec_yd got
    # slightly WORSE (its thin bins rarely clear 300 rows), so it stays unshifted.
    SHIP=[m for m in mk if out[m]['fix']['ll'] < out[m]['base']['ll']]
    # Never fit on the season being shadow-tracked: drop the newest season in
    # the data (the live one), or the side-by-side would grade itself.
    LIVE=max(t for m in mk for t in SEAS[m] if t!='fit')
    pub={"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
         "method": "logit shift by games-of-history bin, fit on season-holdout P(over) (calibrated)",
         "bins": [[a, (b if b < 10**6 else None)] for a,b in BINS],
         "history": "prior-season games + in-season games before this week (raw count, uncapped)",
         "min_rows_per_bin": 300, "fit_seasons": sorted({r for m in mk for r in SEAS[m] if r!='fit' and r<LIVE}),
         "status": "shadow", "markets": {}, "excluded": {}}
    for m in mk:
        tags=[t for t in SEAS[m] if t!='fit']
        rows=[(T,g,p,h) for T,(p,g,h) in zip(tags,graded[m]) if T<LIVE]
        if m in SHIP:
            pub["markets"][m]={"shift":[round(fit_b([(p,h) for _,g,p,h in rows if binof(g)==i]),4) for i in range(len(BINS))],
                               "oos_ll":[out[m]['base']['ll'], out[m]['fix']['ll']]}
        else:
            pub["excluded"][m]={"reason":"nested walk-forward did not improve OOS log-loss","oos_ll":[out[m]['base']['ll'], out[m]['fix']['ll']]}
    json.dump(pub,open(os.path.join(ROOT,'data','prop_history_shift.json'),'w'),indent=1)
    print('published', list(pub['markets']), 'excluded', list(pub['excluded']))
