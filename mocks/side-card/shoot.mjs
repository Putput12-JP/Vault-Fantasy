// Real rendered screenshots of the mocks through Chrome's DevTools protocol (true phone-width emulation; plain --window-size clamps at 500px).
// Usage: node mocks/side-card/shoot.mjs http://localhost:4188/mocks/side-card
import { spawn } from 'node:child_process';
import { writeFileSync, mkdirSync, mkdtempSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
const base = process.argv[2] || 'http://localhost:4188/mocks/side-card';
const out = join(dirname(fileURLToPath(import.meta.url)), 'shots'); mkdirSync(out, { recursive: true });
const port = 9333, chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const proc = spawn(chrome, ['--headless=new', '--remote-debugging-port=' + port, '--user-data-dir=' + mkdtempSync(join(tmpdir(), 'sc-')), '--hide-scrollbars', 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let tabs; for (let i = 0; i < 40; i++) { try { tabs = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); if (tabs.length) break; } catch (e) {} await sleep(250); }
const ws = new WebSocket(tabs.find(t => t.type === 'page').webSocketDebuggerUrl); await new Promise(r => ws.onopen = r);
let id = 0; const wait = new Map(); ws.onmessage = m => { const d = JSON.parse(m.data); if (d.id && wait.has(d.id)) { wait.get(d.id)(d.result); wait.delete(d.id); } };
const send = (method, params = {}) => new Promise(r => { wait.set(++id, r); ws.send(JSON.stringify({ id, method, params })); });
await send('Page.enable');
const STATES = ['proven', 'star', 'total', 'none', 'losers', 'excluded', 'frozen', 'thin', 'empty'];
const jobs = [];
for (const page of ['sharp-money', 'nba']) {
  jobs.push([`${page}-desktop-star`, `${page}.html?state=star`, 1280, 900, 1]);
  jobs.push([`${page}-desktop-open`, `${page}.html?state=frozen&open=1`, 1280, 900, 1]);
  jobs.push([`${page}-mobile-open`, `${page}.html?state=losers&open=1`, 390, 844, 2]);
  jobs.push([`${page}-desktop-all`, `${page}.html`, 1280, 900, 1]);
  jobs.push([`${page}-desktop-light`, `${page}.html?theme=light&state=star`, 1280, 900, 1]);
  for (const s of STATES) jobs.push([`${page}-mobile-${s}`, `${page}.html?state=${s}`, 390, 844, 2]);
}
for (const [name, path, w, h, dpr] of jobs) {
  await send('Emulation.setDeviceMetricsOverride', { width: w, height: h, deviceScaleFactor: dpr, mobile: w < 768 });
  await send('Page.navigate', { url: `${base}/${path}` }); await sleep(1800);
  const { result } = await send('Runtime.evaluate', { expression: 'document.documentElement.scrollHeight' });
  await send('Emulation.setDeviceMetricsOverride', { width: w, height: result.value, deviceScaleFactor: dpr, mobile: w < 768 }); await sleep(300);
  const { data } = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(join(out, name + '.png'), Buffer.from(data, 'base64')); console.log(name, w + 'x' + result.value);
}
ws.close(); proc.kill();
