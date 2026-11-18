import json,glob,collections,math
rows=[]
for f in glob.glob('br/pm_record/cards/*/*.jsonl'):
    for l in open(f):
        d=json.loads(l)
        if d.get('kind')=='result' and d['play']=='sf' and d['variant']=='all' and d['status']=='graded' and d['res'] in('win','loss'): rows.append(d)
print(len(rows))
def agg(rs):
    n=len(rs); w=sum(1 for r in rs if r['res']=='win'); u=sum(r['units_pl'] for r in rs); st=sum(r['units'] for r in rs); fl=sum(r['flat'] for r in rs)
    return f"{w}-{n-w} units {u:+.2f} on {st:.0f}u staked ({u/st*100 if st else 0:+.1f}%) flat {fl/n*100:+.1f}% n={n}"
def by(name,key):
    print('\n--',name)
    g=collections.defaultdict(list)
    for r in rows: g[key(r)].append(r)
    for k in sorted(g,key=lambda x:str(x)): print(f' {str(k):14s}',agg(g[k]))
by('sport',lambda r:r['sport'])
by('group',lambda r:r['group'])
by('sport x group',lambda r:(r['sport'],r['group']))
by('rung',lambda r:r.get('rung'))
by('units',lambda r:r['units'] if r['units']<=3 else '4+')
by('price bucket',lambda r:'<.35' if r['price']<.35 else '.35-.5' if r['price']<.5 else '.5-.65' if r['price']<.65 else '.65-.8' if r['price']<.8 else '>.8')
# implied expectation: mean price vs actual win rate
for sp in ['nba','nfl','cfb','cbb']:
    rs=[r for r in rows if r['sport']==sp]
    print(sp,'mean price',round(sum(r['price'] for r in rs)/len(rs),3),'win rate',round(sum(1 for r in rs if r['res']=='win')/len(rs),3),len(rs))
