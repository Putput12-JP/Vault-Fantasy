import json,subprocess,datetime,concurrent.futures as cf
def get(u):
    try: return json.loads(subprocess.run(['curl','-s','--compressed','--max-time','30',u],capture_output=True).stdout)
    except Exception: return {}
def game(ev):
    e=ev['id'];tip=ev['date']
    o=get(f'https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/{e}/competitions/{e}/odds')
    r={'id':e,'tip':tip,'prov':[],'props':0,'pre':0}
    for i in o.get('items',[]):
        r['prov'].append(i['provider']['name'])
        if 'propBets' in i:
            p=get(i['propBets']['$ref'].replace('http:','https:')+'&limit=2000')
            its=p.get('items',[]);r['props']+=len(its)
            r['pre']+=sum(1 for x in its if x.get('lastUpdated','9')[:16]<tip[:16])
    return r
d=datetime.date(2025,10,21);days=[]
while d<=datetime.date(2026,6,20): days.append(d);d+=datetime.timedelta(days=4)
evs=[]
with cf.ThreadPoolExecutor(8) as ex:
    for s in ex.map(lambda d:get(f'https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={d:%Y%m%d}'),days): evs+=s.get('events',[])
with cf.ThreadPoolExecutor(8) as ex: res=list(ex.map(game,evs))
json.dump(res,open('scan.json','w'))
from collections import defaultdict
m=defaultdict(lambda:[0,0,0,0])
for r in res:
    k=r['tip'][:7];m[k][0]+=1;m[k][1]+=bool(r['prov']);m[k][2]+=r['props']>0;m[k][3]+=r['pre']>0
print('month games w/lines w/props w/pre-tip-props')
for k in sorted(m): print(k,*m[k])
