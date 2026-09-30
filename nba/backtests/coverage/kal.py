import json,subprocess,sys
K='https://api.elections.kalshi.com/trade-api/v2'
def get(u): return json.loads(subprocess.run(['curl','-s','--max-time','30',u],capture_output=True).stdout or '{}')
for s in sys.argv[1:]:
    cur='';n=0;first='9';last='';vol=0;games=set();pages=0
    while pages<60:
        d=get(f'{K}/historical/markets?series_ticker={s}&limit=1000'+(f'&cursor={cur}' if cur else ''))
        m=d.get('markets',[]);pages+=1
        for x in m:
            n+=1;c=x.get('close_time','');first=min(first,c);last=max(last,c);vol+=float(x.get('volume_fp') or x.get('volume') or 0);games.add(x.get('event_ticker'))
        cur=d.get('cursor')
        if not cur or not m: break
    print(s,'markets',n,'events',len(games),first[:10],'->',last[:10],'vol',round(vol),'(capped' if pages>=60 else '')
