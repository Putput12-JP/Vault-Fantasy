import json,glob,pickle,collections
rows=[]
mk={}
for sp in ['nba','nfl','cfb','cbb']:
    m=json.load(open(f'led/pm_ledger/markets/{sp}.json')); 
    for k,v in m.items(): mk[k]=v
    for f in sorted(glob.glob(f'led/pm_ledger/bets/{sp}/*.jsonl')):
        for l in open(f):
            d=json.loads(l)
            rows.append((d['w'],sp,d['cid'],d['oi'],d['avg'],d['stake'],d['pnl'],d['res'],d['gst'],d['settled_at'],d['first'],d['last'],d['mt'],d['hedged'],d['split'],d['src'],d['sh'],d['exited'],d.get('post',0)))
print(len(rows))
pickle.dump((rows,mk),open('rows.pkl','wb'))
c=collections.Counter((r[1],r[15]) for r in rows); print(c)
c=collections.Counter((r[1],r[12]) for r in rows); print(c)
import datetime
ts=[r[8] for r in rows]; print(datetime.datetime.fromtimestamp(min(ts)),datetime.datetime.fromtimestamp(max(ts)))
