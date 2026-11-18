import { spawn } from 'node:child_process';
import { writeFileSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const base='http://localhost:4210/projections.html';
const out=join(dirname(fileURLToPath(import.meta.url)),'shots');
const port=9334, chrome='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
spawn(chrome,['--headless=new','--remote-debugging-port='+port,'--user-data-dir='+mkdtempSync(join(tmpdir(),'au-')),'--hide-scrollbars','about:blank'],{stdio:'ignore'});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let tabs; for(let i=0;i<40;i++){try{tabs=await (await fetch(`http://127.0.0.1:${port}/json`)).json();if(tabs.length)break}catch(e){}await sleep(250)}
const ws=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl); await new Promise(r=>ws.onopen=r);
let id=0; const wait=new Map(); ws.onmessage=m=>{const d=JSON.parse(m.data); if(d.id&&wait.has(d.id)){wait.get(d.id)(d.result);wait.delete(d.id)}};
const send=(method,params={})=>new Promise(r=>{wait.set(++id,r);ws.send(JSON.stringify({id,method,params}))});
await send('Page.enable'); await send('Runtime.enable');
const pages=['summary','lab','slate','matchups','sim','propsim','wire','lines','games','propboard','sharps','pairs','bankroll','mybets','track','btlab','health','profile'];
const metrics={};
for(const [name,w,h,mobile] of [['desktop',1400,900,false],['mobile',390,844,true]]){
 await send('Emulation.setDeviceMetricsOverride',{width:w,height:h,deviceScaleFactor:1,mobile});
 for(const p of pages){
  await send('Page.navigate',{url:base+'#'+p}); await sleep(900);
  await send('Runtime.evaluate',{expression:`location.hash='#${p}';location.reload()`}); await sleep(3500);
  const m=(await send('Runtime.evaluate',{returnByValue:true,expression:`(()=>{
   const vis=e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&getComputedStyle(e).visibility!=='hidden'};
   const main=document.body;
   const ps=[...main.querySelectorAll('p,div,span')].filter(e=>vis(e)&&e.children.length===0&&e.textContent.trim().length>140&&!e.closest('nav,aside,script,style'));
   const long=ps.map(e=>({len:e.textContent.trim().length,top:Math.round(e.getBoundingClientRect().top+scrollY),txt:e.textContent.trim().slice(0,110)})).sort((a,b)=>a.top-b.top);
   const firstTable=[...main.querySelectorAll('table,.card,canvas,svg')].find(vis);
   return {hash:location.hash,h:document.documentElement.scrollHeight,long:long.slice(0,8),words:(main.innerText||'').split(/\\s+/).length,empty:/no data|nothing|no plays|none yet|no games|empty|coming soon/i.test(main.innerText)}})()`})).result.value;
  metrics[name+'-'+p]=m;
  const s=await send('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  writeFileSync(join(out,`${p}-${name}.png`),Buffer.from(s.data,'base64'));
 }
}
writeFileSync(join(out,'..','metrics.json'),JSON.stringify(metrics,null,1));
process.exit(0);
