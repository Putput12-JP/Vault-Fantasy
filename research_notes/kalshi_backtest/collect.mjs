#!/usr/bin/env node
// Kalshi NFL prop backtest collector. Resumable: caches to ./cache/*.json
// Step 1 markets (historical + live settled), Step 2 hourly candles for liquid markets.
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'node:fs';
const B='https://api.elections.kalshi.com/trade-api/v2';
const SERIES={KXNFLRSHATT:'rush_att',KXNFLRSHYDS:'rush_yd',KXNFLRECYDS:'rec_yd',KXNFLREC:'rec',KXNFLPASSYDS:'pass_yd',KXNFLPASSATT:'pass_att',KXNFLPASSINT:'pass_int'};
const MIN_VOL=+process.env.MIN_VOL||300;
mkdirSync('cache',{recursive:true});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let last=0; const GAP=+process.env.GAP||120;
async function g(u){
  for(let i=0;i<10;i++){
    const w=GAP-(Date.now()-last); if(w>0) await sleep(w); last=Date.now();
    const r=await fetch(B+u,{headers:{'User-Agent':'VaultFantasy/1.0'}});
    if(r.status===429){await sleep(1500*(i+1));continue}
    if(!r.ok) return {err:r.status};
    return r.json();
  }
  return {err:429};
}
const slim=m=>({t:m.ticker,e:m.event_ticker,k:m.floor_strike,res:m.result,ot:m.open_time,ct:m.close_time,xt:m.expected_expiration_time,v:+m.volume_fp||0,who:(m.yes_sub_title||'').replace(/:.*/,''),sub:m.yes_sub_title});
async function markets(){
  const f='cache/markets.json'; if(existsSync(f)) return JSON.parse(readFileSync(f));
  const out=[];
  for(const [s,mk] of Object.entries(SERIES)){
    for(const [tier,path,extra] of [['hist','/historical/markets',''],['live','/markets','&status=settled']]){
      let c='',n=0;
      for(let i=0;i<80;i++){
        const j=await g(`${path}?series_ticker=${s}&limit=1000${extra}${c?'&cursor='+c:''}`);
        if(j.err){console.log('ERR',s,tier,j.err);break}
        for(const m of j.markets){ if(m.result!=='yes'&&m.result!=='no') continue; out.push({...slim(m),mk,tier}); n++; }
        c=j.cursor; if(!c) break;
      }
      console.log(s,tier,n);
    }
  }
  writeFileSync(f,JSON.stringify(out)); return out;
}
(async()=>{
  const all=await markets();
  console.log('markets',all.length,'liquid',all.filter(m=>m.v>=MIN_VOL).length);
  const cf='cache/candles.json'; const C=existsSync(cf)?JSON.parse(readFileSync(cf)):{};
  const todo=all.filter(m=>m.v>=MIN_VOL&&!(m.t in C));
  console.log('candles todo',todo.length);
  let n=0;
  for(const m of todo){
    const st=Math.floor(Date.parse(m.ot)/1000), en=Math.floor(Date.parse(m.xt||m.ct)/1000);
    const path=m.tier==='hist'?`/historical/markets/${m.t}/candlesticks`:`/series/${m.t.split('-')[0]}/markets/${m.t}/candlesticks`;
    const j=await g(`${path}?start_ts=${st}&end_ts=${en}&period_interval=60`);
    if(j.err){ if(j.err===429){console.log('rate-limited, stopping');break} C[m.t]=null; }
    else C[m.t]=(j.candlesticks||[]).map(c=>[c.end_period_ts,+c.yes_bid?.close||0,+c.yes_ask?.close||0,+c.volume||0,+c.yes_bid?.close>=0?1:0]);
    if(++n%200===0){writeFileSync(cf,JSON.stringify(C));console.log('candles',n,'/',todo.length)}
  }
  writeFileSync(cf,JSON.stringify(C)); console.log('done',Object.keys(C).length);
})();
