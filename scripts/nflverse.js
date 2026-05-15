/*
  nflverse.js - Vault Fantasy nflverse data layer
  Fetches pre-processed JSON from GitHub Pages (same domain, no CORS).
  Data updated daily by GitHub Actions.

  API:
    initNflverse()              - load data (called automatically on page load)
    getNflversePlayer(name)     - get player stats object
    getNflverseSnaps(name)      - get snap count object
    getNflverseInjury(name)     - get injury status
    renderNflverseCard(name,el) - render full stat card into an element
    nflverseLoaded              - boolean, true when data is ready
*/

const NFLVERSE_BASE = window.location.href.includes('github.io')
  ? 'https://putput12-jp.github.io/Vault-Fantasy/data'
  : '/data';

let _nflStats=null, _nflSnaps=null, _nflInjuries=null, _nflMeta=null;
let _nflLoading=false, _nflLoadProm=null;
window.nflverseLoaded = false;

async function initNflverse() {
  if (window.nflverseLoaded) return;
  if (_nflLoading) return _nflLoadProm;
  _nflLoading = true;
  _nflLoadProm = (async () => {
    try {
      const [sR,snR,iR,mR] = await Promise.all([
        fetch(NFLVERSE_BASE+'/nflverse_stats.json'),
        fetch(NFLVERSE_BASE+'/nflverse_snaps.json'),
        fetch(NFLVERSE_BASE+'/nflverse_injuries.json').catch(()=>null),
        fetch(NFLVERSE_BASE+'/nflverse_meta.json').catch(()=>null),
      ]);
      if (!sR.ok) throw new Error('stats '+sR.status);
      if (!snR.ok) throw new Error('snaps '+snR.status);
      _nflStats    = await sR.json();
      _nflSnaps    = await snR.json();
      _nflInjuries = iR?.ok ? await iR.json() : {};
      _nflMeta     = mR?.ok ? await mR.json() : null;
      window.nflverseLoaded = true;
      console.log('[Vault] nflverse loaded -', Object.keys(_nflStats).length, 'players, updated', _nflMeta?.updated_at?.slice(0,10));
    } catch(e) { console.error('[Vault] nflverse load failed:', e); throw e; }
    finally { _nflLoading = false; }
  })();
  return _nflLoadProm;
}

function _fuzzy(map, name) {
  if (!map||!name) return null;
  if (map[name]) return map[name];
  const n = s => s.toLowerCase().replace(/[^a-z]/g,'');
  const t = n(name);
  for (const k of Object.keys(map)) { if (n(k)===t) return map[k]; }
  return null;
}

function getNflversePlayer(name)  { return _fuzzy(_nflStats,name); }
function getNflverseSnaps(name)   { return _fuzzy(_nflSnaps,name); }
function getNflverseInjury(name)  { return _fuzzy(_nflInjuries,name); }
function getNflverseMeta()        { return _nflMeta; }

const posColor = {QB:'#e24b4a',RB:'#3DCC7A',WR:'#7bd0ff',TE:'#f5c842'};
const posBg    = {QB:'rgba(226,75,74,.1)',RB:'rgba(61,204,122,.1)',WR:'rgba(123,208,255,.1)',TE:'rgba(245,200,66,.1)'};

function renderNflverseCard(name, el) {
  if (!el) return;
  const p = getNflversePlayer(name);
  const s = getNflverseSnaps(name);
  const inj = getNflverseInjury(name);
  const meta = getNflverseMeta();
  if (!p) { el.innerHTML='<div style="font-size:12px;color:var(--muted);padding:8px 0">No nflverse data for '+name+'</div>'; return; }

  const pos = p.pos||'?';
  const col = posColor[pos]||'#909097';
  const bg  = posBg[pos]||'rgba(255,255,255,.06)';
  const wks = p.weeks||[];
  const snpWks = s?.weeks||[];
  const ssn = p.season||{};
  const maxPts = Math.max(...wks.map(w=>w.pts||0),1);
  const maxSnap = Math.max(...snpWks.map(w=>w.off||0),1);

  const ptsBars = wks.map(w=>{
    const h=Math.max(2,Math.round((w.pts/maxPts)*36));
    return '<div title="Wk '+w.wk+': '+w.pts+' pts" style="flex:1;height:'+h+'px;background:'+(w.pts>=ssn.avg_pts?col:'rgba(255,255,255,.15)')+';border-radius:1px 1px 0 0;min-width:4px"></div>';
  }).join('');

  const snapBars = snpWks.map(w=>{
    const v=w.off||0, h=Math.max(2,Math.round((v/maxSnap)*36));
    return '<div title="Wk '+w.wk+': '+v+'%" style="flex:1;height:'+h+'px;background:'+(v<50?'rgba(226,75,74,.6)':'rgba(123,208,255,.7)')+';border-radius:1px 1px 0 0;min-width:4px"></div>';
  }).join('');

  const trendUp = p.l4w_avg >= ssn.avg_pts;
  const trendBadge = wks.length>=4
    ? '<span style="font-size:10px;padding:2px 7px;border-radius:20px;background:'+(trendUp?'rgba(61,204,122,.15)':'rgba(226,75,74,.15)')+';color:'+(trendUp?'#3DCC7A':'#e24b4a')+';">'+(trendUp?'↑':'↓')+' L4W '+p.l4w_avg+'</span>'
    : '';

  const fresh = meta?.updated_at
    ? '<span style="font-size:9px;color:var(--muted);font-family:var(--font-mono)">Updated '+meta.updated_at.slice(0,10)+'</span>'
    : '';

  let statBoxes = '<div style="background:'+bg+';border:1px solid '+col+'22;border-radius:8px;padding:8px 10px"><div style="font-size:9px;color:var(--muted);font-family:var(--font-mono);text-transform:uppercase;margin-bottom:2px">PPR pts/g</div><div style="font-size:20px;font-weight:700;color:var(--text);font-family:var(--font-mono)">'+(ssn.avg_pts||'—')+'</div><div style="font-size:10px;color:var(--muted)">'+(ssn.games||0)+' games</div></div>';
  const box=(lbl,val)=>'<div style="background:'+bg+';border:1px solid '+col+'22;border-radius:8px;padding:8px 10px"><div style="font-size:9px;color:var(--muted);font-family:var(--font-mono);text-transform:uppercase;margin-bottom:2px">'+lbl+'</div><div style="font-size:18px;font-weight:700;color:var(--text);font-family:var(--font-mono)">'+(val||'—')+'</div></div>';
  if (pos==='QB') statBoxes+=box('Pass Yds/g',ssn.avg_pyds)+box('Pass TDs/g',ssn.avg_ptds)+box('Rush Yds/g',ssn.avg_ryds);
  else if (pos==='RB') statBoxes+=box('Carries/g',ssn.avg_car)+box('Rush Yds/g',ssn.avg_ryds)+box('Targets/g',ssn.avg_tgt);
  else statBoxes+=box('Targets/g',ssn.avg_tgt)+box('Rec Yds/g',ssn.avg_recyds);
  if (s?.avg_off!=null) statBoxes+='<div style="background:rgba(123,208,255,.07);border:1px solid rgba(123,208,255,.15);border-radius:8px;padding:8px 10px"><div style="font-size:9px;color:var(--muted);font-family:var(--font-mono);text-transform:uppercase;margin-bottom:2px">Snap %</div><div style="font-size:20px;font-weight:700;color:var(--sky);font-family:var(--font-mono)">'+s.avg_off+'%</div></div>';

  let advHtml = '';
  if (['WR','TE','FB'].includes(pos) && (ssn.avg_ts||ssn.avg_wopr)) {
    const m=(lbl,val,max,c)=>{const pct=val!=null?Math.min(100,(val/max)*100):0;return '<div style="margin-bottom:7px"><div style="display:flex;justify-content:space-between;margin-bottom:3px"><span style="font-size:10px;color:var(--muted);font-family:var(--font-mono)">'+lbl+'</span><span style="font-size:11px;font-weight:700;color:'+c+';font-family:var(--font-mono)">'+(val!=null?val:'—')+'</span></div><div style="height:4px;background:rgba(255,255,255,.08);border-radius:2px;overflow:hidden"><div style="height:100%;width:'+pct.toFixed(0)+'%;background:'+c+';border-radius:2px"></div></div></div>';};
    advHtml='<div style="border-top:1px solid rgba(255,255,255,.06);padding-top:10px;margin-top:8px"><div style="font-size:9px;color:var(--muted);font-family:var(--font-mono);text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px">ADVANCED METRICS</div>'
      +(ssn.avg_ts!=null?m('Target Share',ssn.avg_ts+'%',35,'#7bd0ff'):'')
      +(ssn.avg_ays!=null?m('Air Yards Share',ssn.avg_ays+'%',35,'#f5c842'):'')
      +(ssn.avg_wopr!=null?m('WOPR',ssn.avg_wopr,0.7,'#3DCC7A'):'')
      +(ssn.avg_racr!=null?m('RACR',ssn.avg_racr,2.0,'#cc003c'):'')
      +'</div>';
  }

  el.innerHTML='<div style="border-top:1px solid rgba(255,255,255,.08);padding:14px 0;margin-top:8px">'
    +'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px"><div style="font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);font-family:var(--font-mono)">NFLVERSE · '+(meta?.season||2024)+' SEASON</div><div style="display:flex;align-items:center;gap:8px">'+trendBadge+' '+fresh+'</div></div>'
    +'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(85px,1fr));gap:8px;margin-bottom:12px">'+statBoxes+'</div>'
    +(wks.length?'<div style="margin-bottom:10px"><div style="font-size:9px;color:var(--muted);font-family:var(--font-mono);text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px">PPR POINTS BY WEEK</div><div style="display:flex;align-items:flex-end;gap:2px;height:36px">'+ptsBars+'</div></div>':'')
    +(snpWks.length?'<div style="margin-bottom:10px"><div style="font-size:9px;color:var(--muted);font-family:var(--font-mono);text-transform:uppercase;letter-spacing:.08em;margin-bottom:5px">SNAP % BY WEEK <span style="font-weight:400;font-size:8px"> · <span style="color:#7bd0ff">■</span> ≥50% <span style="color:#e24b4a">■</span> &lt;50%</span></div><div style="display:flex;align-items:flex-end;gap:2px;height:36px">'+snapBars+'</div></div>':'')
    +advHtml+'</div>';
}

if (document.readyState==='loading') {
  document.addEventListener('DOMContentLoaded', ()=>initNflverse().catch(console.warn));
} else {
  initNflverse().catch(console.warn);
}

window.initNflverse=initNflverse;
window.getNflversePlayer=getNflversePlayer;
window.getNflverseSnaps=getNflverseSnaps;
window.getNflverseInjury=getNflverseInjury;
window.getNflverseMeta=getNflverseMeta;
window.renderNflverseCard=renderNflverseCard;
