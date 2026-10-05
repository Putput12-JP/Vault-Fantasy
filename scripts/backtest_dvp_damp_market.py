#!/usr/bin/env python3
# Market-line diagnostics for backtest_dvp_damp.py: does the shipped DvP term flip
# prop sides correctly vs 2026 closing lines beyond chance? Permutation null
# (shuffle multipliers within position), defense-week cluster bootstrap, QB detail.
# Usage: python3 scripts/backtest_dvp_damp_market.py
import importlib.util, json, os, random, statistics
from collections import defaultdict, Counter
spec=importlib.util.spec_from_file_location("bt",os.path.join(os.path.dirname(os.path.abspath(__file__)), "backtest_dvp_damp.py")); bt=importlib.util.module_from_spec(spec); spec.loader.exec_module(bt)
model=json.load(open(os.path.join(bt.DATA,"prop_model.json")))["markets"]
ctx=bt.build_ctx([2025,2026]); hist=bt.player_hist([2025,2026])
G=(8,0.5,0.2)
B=json.load(open(os.path.join(bt.DATA,"bet_results.json")))["props"]
seen=set(); rows=[]
for r in B:
  mkt,pos=r.get("market"),r.get("pos")
  if pos not in bt.ALLPOS or not(mkt in bt.MARKETS or mkt in bt.COMBOS): continue
  key=(bt.nkey(r["name"]),mkt,r["week"])
  if key in seen: continue
  seen.add(key)
  line,act,wk=bt.num(r.get("line_close")) or bt.num(r.get("line_open")),bt.num(r.get("actual")),int(r["week"])
  if line is None or act is None or act==line: continue
  h=hist.get((bt.nkey(r["name"]),pos)) or []
  idx=next((i for i,(s,w,_) in enumerate(h) if s==2026 and w==wk),None)
  if idx is None: continue
  prior=[x[2] for x in h[max(0,idx-17):idx]]
  c=ctx.get((2026,wk,bt.tm(r.get("opp"))))
  if not c: continue
  parts=bt.COMBOS.get(mkt,(mkt,))
  projs=[bt.project(model[m],prior) if pos in bt.MARKETS[m] else 0.0 for m in parts]
  if any(p is None for p in projs): continue
  base=sum(projs); m=c[pos][3]
  rows.append(dict(mkt=mkt,pos=pos,wk=wk,opp=bt.tm(r.get("opp")),line=line,over=act>line,base=base,prod=base*m,pm=m,dm=bt.damp(c[pos],*G),
                   vproj=bt.num(r.get("proj")),side=r.get("side")))
print("n",len(rows),"over-rate",round(sum(x['over'] for x in rows)/len(rows),3))
print("base picks over:",round(sum(x['base']>x['line'] for x in rows)/len(rows),3),"| prod picks over:",round(sum(x['prod']>x['line'] for x in rows)/len(rows),3))
print("mean prod mult",round(statistics.fmean(x['pm'] for x in rows),4), "| by week", {w:round(statistics.fmean(x['pm'] for x in rows if x['wk']==w),3) for w in (1,2,3,4)})
fl=[x for x in rows if (x['prod']>x['line'])!=(x['base']>x['line'])]
for d in ("to_under","to_over"):
  sub=[x for x in fl if (x['prod']>x['line'])==(d=="to_over")]
  if sub: print(d,len(sub),"wins",round(sum((x['prod']>x['line'])==x['over'] for x in sub)/len(sub),3))
print("flips by week:",{w:(len(s:=[x for x in fl if x['wk']==w]), round(sum((x['prod']>x['line'])==x['over'] for x in s)/len(s),3) if s else None) for w in (1,2,3,4)})
print("flips by pos:",{p:(len(s:=[x for x in fl if x['pos']==p]), round(sum((x['prod']>x['line'])==x['over'] for x in s)/len(s),3) if s else None) for p in bt.ALLPOS})
cl=Counter((x['opp'],x['wk']) for x in fl); print("distinct defense-weeks among flips:",len(cl),"top:",cl.most_common(6))
# cluster bootstrap by defense-week
groups=defaultdict(list)
for x in fl: groups[(x['opp'],x['wk'])].append((x['prod']>x['line'])==x['over'])
keys=list(groups); random.seed(7); bs=[]
for _ in range(4000):
  smp=[groups[random.choice(keys)] for _ in keys]; t=sum(len(g) for g in smp); bs.append(sum(sum(g) for g in smp)/t)
bs.sort(); print("cluster-bootstrap 95% CI for flip win rate:",round(bs[100],3),round(bs[3900],3))
# Does a pure over->under bias correction do the same? shrink base by k so the same # of overs flip
for f in (0.97,0.95,0.93):
  sub=[x for x in rows if (x['base']*f>x['line'])!=(x['base']>x['line'])]
  if sub: print(f"flat x{f}: flips {len(sub)}, flipped side wins {round(sum((x['base']*f>x['line'])==x['over'] for x in sub)/len(sub),3)}")
# what does the LIVE vault proj say (bet_results proj, includes prod oppMult): side hit
vr=[x for x in rows if x['vproj'] is not None]; print("live Vault proj side wins",round(sum((x['vproj']>x['line'])==x['over'] for x in vr)/len(vr),3),"n",len(vr))

print("\n--- permutation null: shuffle the prod multipliers across props (within position) ---")
def flipstats(rows, mults):
  w=n=0; tot=0
  for x,m in zip(rows,mults):
    if (x['base']*m>x['line'])!=(x['base']>x['line']):
      n+=1; w+=((x['base']*m>x['line'])==x['over'])
    tot+=((x['base']*m>x['line'])==x['over'])
  return n,w,tot/len(rows)
for scope in ("ALL","QB","RB","WR","TE"):
  rs=[x for x in rows if scope=="ALL" or x['pos']==scope]
  n0,w0,t0=flipstats(rs,[x['pm'] for x in rs])
  sims=[]; tots=[]
  for _ in range(3000):
    ms=[x['pm'] for x in rs]
    if scope=="ALL":
      by=defaultdict(list)
      for i,x in enumerate(rs): by[x['pos']].append(i)
      ms=ms[:]
      for p,ix in by.items():
        vals=[ms[i] for i in ix]; random.shuffle(vals)
        for i,v in zip(ix,vals): ms[i]=v
    else: random.shuffle(ms)
    n,w,t=flipstats(rs,ms); sims.append(w/n if n else 0.5); tots.append(t)
  real=w0/n0 if n0 else None
  p=sum(s>=real for s in sims)/len(sims); pt=sum(s>=t0 for s in tots)/len(tots)
  print(f"{scope:4} real flips {n0:4} win {real:.3f} | shuffled flips win {statistics.fmean(sims):.3f} (p={p:.3f}) | overall side-hit real {t0:.3f} vs shuffled {statistics.fmean(tots):.3f} (p={pt:.3f})")
# damped global for comparison
n0,w0,t0=flipstats(rows,[x['dm'] for x in rows]); print(f"d_glob: flips {n0} win {w0/n0:.3f}, overall side-hit {t0:.3f}")

print("\n--- QB detail ---")
q=[x for x in rows if x['pos']=="QB" and (x['prod']>x['line'])!=(x['base']>x['line'])]
for m in sorted(set(x['mkt'] for x in q)):
  s=[x for x in q if x['mkt']==m]; print(f"  {m:13} flips {len(s):3} win {sum((x['prod']>x['line'])==x['over'] for x in s)/len(s):.3f}")
print("  by week",{w:(len(s:=[x for x in q if x['wk']==w]), round(sum((x['prod']>x['line'])==x['over'] for x in s)/len(s),3) if s else None) for w in (1,2,3,4)})
g=defaultdict(list)
for x in q: g[(x['opp'],x['wk'])].append((x['prod']>x['line'])==x['over'])
print("  QB defense-weeks:",len(g)); keys=list(g); bs=[]
for _ in range(4000):
  smp=[g[random.choice(keys)] for _ in keys]; t=sum(len(a) for a in smp); bs.append(sum(sum(a) for a in smp)/t)
bs.sort(); print("  cluster CI",round(bs[100],3),round(bs[3900],3))
# leave-one-defense-out: drop each opp entirely
opps=set(x['opp'] for x in q); lo=[]
for o in opps:
  s=[x for x in q if x['opp']!=o]; lo.append(sum((x['prod']>x['line'])==x['over'] for x in s)/len(s))
print("  leave-one-defense-out min/max",round(min(lo),3),round(max(lo),3))
