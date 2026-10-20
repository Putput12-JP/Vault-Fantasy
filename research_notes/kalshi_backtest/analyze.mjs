import { readFileSync } from 'node:fs';
const M=JSON.parse(readFileSync('cache/markets.json')), C=JSON.parse(readFileSync('cache/candles.json'));
const HRS=3, LEAD=1800, MAXSPR=+process.env.MAXSPR||0.10;
const G={};
{const L=readFileSync('cache/games.csv','utf8').split('\n');const H=L[0].split(',');const ix=n=>H.indexOf(n);
 const nt=t=>({JAX:'JAC',WSH:'WAS',LA:'LAR',OAK:'LV',SD:'LAC',STL:'LAR'}[t]||t);
 const et=(d,t)=>{const [h,mi]=t.split(':').map(Number);const [y,mo,da]=d.split('-').map(Number);
  for(const off of [4,5]){const u=Date.UTC(y,mo-1,da,h+off,mi);const p=new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'numeric',hour12:false}).format(u);if(+p%24===h)return u/1000}return null};
 for(const l of L.slice(1)){const c=l.split(',');const d=c[ix('gameday')],t=c[ix('gametime')];if(!d||!t||d<'2025-08')continue;
  const k=d+'|'+nt(c[ix('away_team')])+nt(c[ix('home_team')]);G[k]=et(d,t)}}
const MON={JAN:'01',FEB:'02',MAR:'03',SEP:'09',OCT:'10',NOV:'11',DEC:'12',AUG:'08'};
const nt2=t=>t;
let koHit=0,koMiss=0;
function kick(m){const tag=m.e.split('-')[1];const mm=/^(\d\d)([A-Z]{3})(\d\d)([A-Z]+)$/.exec(tag);if(!mm)return null;
 const d=`20${mm[1]}-${MON[mm[2]]}-${mm[3]}`;const tm=mm[4];
 for(const n of [2,3]){const a=tm.slice(0,n),h=tm.slice(n);const v=G[d+'|'+({JAX:'JAC',WSH:'WAS',LA:'LAR'}[a]||a)+({JAX:'JAC',WSH:'WAS',LA:'LAR'}[h]||h)];if(v)return v}return null}
const rows=[];
for(const m of M){
  const cs=C[m.t]; if(!cs||!cs.length) continue;
  let k0=kick(m);if(k0)koHit++;else koMiss++;const ko=(k0??Date.parse(m.xt||m.ct)/1000-HRS*3600)-LEAD;
  let c=null; for(const x of cs){ if(x[0]<=ko && x[2]>0 && x[2]>x[1]) c=x; }
  if(!c) continue;
  const spr=c[2]-c[1]; if(spr>MAXSPR) continue;
  rows.push({mk:m.mk,tier:m.tier,p:(c[1]+c[2])/2,y:m.res==='yes'?1:0,spr,k:m.k,v:m.v});
}
const brier=a=>a.reduce((s,r)=>s+(r.p-r.y)**2,0)/a.length;
const ll=a=>a.reduce((s,r)=>{const p=Math.min(.99,Math.max(.01,r.p));return s-(r.y?Math.log(p):Math.log(1-p))},0)/a.length;
const mean=(a,f)=>a.reduce((s,r)=>s+f(r),0)/a.length;
const bins=[[0,.1],[.1,.2],[.2,.3],[.3,.4],[.4,.5],[.5,.6],[.6,.7],[.7,.8],[.8,.9],[.9,1.01]];
function rel(a){return bins.map(([lo,hi])=>{const b=a.filter(r=>r.p>=lo&&r.p<hi);if(b.length<30)return null;const mp=mean(b,r=>r.p),hr=mean(b,r=>r.y);const se=Math.sqrt(hr*(1-hr)/b.length);return {bin:`${lo.toFixed(1)}-${Math.min(hi,1).toFixed(1)}`,n:b.length,fair:+mp.toFixed(3),hit:+hr.toFixed(3),gap:+(hr-mp).toFixed(3),z:+((hr-mp)/Math.max(se,1e-9)).toFixed(1)}}).filter(Boolean)}
function summ(lab,a){ if(a.length<50)return; const base=mean(a,r=>r.y); const bb=mean(a,r=>(base-r.y)**2);
  console.log(`${lab.padEnd(18)} n=${String(a.length).padStart(5)}  fair=${mean(a,r=>r.p).toFixed(3)} hit=${base.toFixed(3)} bias=${(base-mean(a,r=>r.p)>=0?'+':'')}${(base-mean(a,r=>r.p)).toFixed(3)}  brier=${brier(a).toFixed(4)} (const ${bb.toFixed(4)}) logloss=${ll(a).toFixed(4)}`)}
console.log('kickoff matched',koHit,'fallback',koMiss);console.log('priced rows',rows.length,'of',M.length,'(spread<=',MAXSPR,')');
console.log('\n== by prop market'); for(const mk of [...new Set(rows.map(r=>r.mk))]) summ(mk,rows.filter(r=>r.mk===mk));
console.log('\n== by tier (hist=2025 season, live=2026)'); for(const t of ['hist','live']) summ(t,rows.filter(r=>r.tier===t));
console.log('\n== market x tier'); for(const mk of [...new Set(rows.map(r=>r.mk))]) for(const t of ['hist','live']) summ(mk+' '+t,rows.filter(r=>r.mk===mk&&r.tier===t));
console.log('\n== by spread'); for(const [lo,hi] of [[0,.02],[.02,.04],[.04,.07],[.07,.101]]) summ(`spr ${lo}-${hi}`,rows.filter(r=>r.spr>=lo&&r.spr<hi));
console.log('\n== reliability: all'); console.table(rel(rows));
for(const mk of ['rec_yd','rec','rush_yd','pass_yd']){console.log('\n== reliability:',mk);console.table(rel(rows.filter(r=>r.mk===mk)))}
