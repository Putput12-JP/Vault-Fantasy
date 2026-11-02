#!/usr/bin/env node
// Motion check: records the box of every visible element under a root on
// each animation frame in a real headless Chrome, then reports motion that
// is never intentional:
//
//   jump    an element that is still, moves more than 2px in one frame, and
//           is still again (a teleport, e.g. a pill re-rendered with no seed)
//   drift   two stacked neighbors that both keep their size but not the gap
//           between them (they glide on different curves)
//   anchor  an open menu/popover/sheet whose top edge moves while its height
//           changes (it should grow down from its anchor)
//   pill    after each --click, the nearest .vrail's .v-pill: live left/width
//           transitions and whether .rail-noanim got set (CLAUDE.md trap 5b)
//
// Why a separate browser: the app's preview tab may never paint, so rAF,
// ResizeObserver and sampled pill positions can't be trusted there. Headless
// Chrome paints, so rAF runs every frame.
//
// Recorder and analysis adapted from stageshow's scripts/jumps-core.mjs
// (MIT, Copyright (c) 2026 Benji Taylor, github.com/benjitaylor/skills).
//
// usage:
//   node scripts/motion-check.mjs <url> [--select "#header-nav"]
//        [--click "#nb-research" --click "#nb-draft" ...] [--gap 900]
//        [--ms 4000] [--wait "<selector>"] [--settle 1500]
//        [--width 1280 | --mobile] [--theme light|vapor|onyx] [--sleeper Putput]
//        [--report out.json]
//
// --sleeper connects that Sleeper user through the setup screen first, so
// pages show real data (CLAUDE.md: load Putput).
//
// Exit code: 0 clean, 1 findings, 2 could not run.

import { existsSync, mkdirSync, readdirSync, statSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { dirname, join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'

// ---- Arguments -------------------------------------------------------------

const args = process.argv.slice(2)
const opt = { select: 'body', click: [], gap: 900, ms: 4000, wait: null, settle: 1500, width: 1280, mobile: false, theme: null, sleeper: null, report: null }
let url
try {
  for (let i = 0; i < args.length; i++) {
    const a = args[i]
    const val = () => {
      if (!args[i + 1] || args[i + 1].startsWith('--')) throw new Error(`${a} requires a value`)
      return args[++i]
    }
    if (a === '--help') { console.log(usage()); process.exit(0) }
    else if (a === '--mobile') opt.mobile = true
    else if (a === '--click') opt.click.push(val())
    else if (/^--(select|wait|theme|sleeper|report)$/.test(a)) opt[a.slice(2)] = val()
    else if (/^--(gap|ms|settle|width)$/.test(a)) {
      const n = Number(val())
      if (!Number.isInteger(n) || n < 0) throw new Error(`${a} must be a whole number`)
      opt[a.slice(2)] = n
    } else if (a.startsWith('--') || url) throw new Error(`unexpected argument: ${a}`)
    else url = a
  }
  if (!url) throw new Error('a URL is required; use --help')
} catch (e) { console.error(`motion-check: ${e.message}`); process.exit(2) }

function usage() {
  return 'usage: node scripts/motion-check.mjs <url> [--select sel] [--click sel ...] [--gap ms] [--ms ms] [--wait sel] [--settle ms] [--width px | --mobile] [--theme name] [--sleeper user] [--report file]'
}

// ---- Browser ---------------------------------------------------------------

// The repo has no package.json, so playwright-core may only exist in the npx
// cache. Try a normal import, then PLAYWRIGHT_CORE, then the newest cached copy.
async function loadChromium() {
  try { return (await import('playwright-core')).chromium } catch {}
  const candidates = []
  if (process.env.PLAYWRIGHT_CORE) candidates.push(process.env.PLAYWRIGHT_CORE)
  const npx = join(homedir(), '.npm', '_npx')
  if (existsSync(npx)) {
    for (const d of readdirSync(npx)) {
      const p = join(npx, d, 'node_modules', 'playwright-core')
      if (existsSync(join(p, 'package.json'))) candidates.push(p)
    }
    candidates.sort((x, y) => statSync(y).mtimeMs - statSync(x).mtimeMs)
  }
  for (const p of candidates) {
    try { return (await import(pathToFileURL(join(p, 'index.mjs')).href)).chromium } catch {}
  }
  console.error('motion-check needs playwright-core. Run once: npx -y playwright-core --version   (or set PLAYWRIGHT_CORE to its folder)')
  process.exit(2)
}

async function launch() {
  const chromium = await loadChromium()
  const path = process.env.CHROME_PATH
  try { return await chromium.launch(path ? { executablePath: path } : { channel: 'chrome' }) } catch {}
  try { return await chromium.launch() } catch {}
  console.error('motion-check: could not start Chrome. Install Google Chrome or set CHROME_PATH.')
  process.exit(2)
}

// ---- In-page recorder (serialized into the page; must stay self-contained) --

function recorder(rootSel) {
  const V = (window.__mc = { frames: [], errors: [], stopped: false, mark: '', elements: 0 })
  const ids = new WeakMap()
  let n = 0
  const label = (el) => {
    const tag = el.tagName.toLowerCase()
    const idp = el.id ? `#${el.id}` : ''
    const cls = typeof el.className === 'string' && el.className.trim() ? '.' + el.className.trim().split(/\s+/)[0] : ''
    const text = (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 18)
    return `${tag}${idp}${cls}${text ? ` "${text}"` : ''}`
  }
  const id = (el) => {
    if (!ids.has(el)) ids.set(el, { n: n++, name: label(el) })
    return ids.get(el)
  }
  const inFlow = (e) => !/absolute|fixed/.test(getComputedStyle(e).position)
  const t0 = performance.now()
  const tick = () => {
    if (V.stopped) return
    try {
      const root = document.querySelector(rootSel)
      if (!root) { requestAnimationFrame(tick); return }
      const box = root.getBoundingClientRect()
      const items = []
      const all = root.querySelectorAll('*')
      V.elements = all.length
      for (const el of all) {
        const r = el.getBoundingClientRect()
        if (r.width * r.height < 16) continue
        // Things that step on purpose: carets, spinners, skeleton shimmer,
        // and anything marked data-snap
        if (el.closest('[data-snap], .spinner, .skel, .v-loading')) continue
        const cs = getComputedStyle(el)
        if (cs.visibility === 'hidden') continue
        // A wrapper that paints nothing can't be seen to jump; its contents
        // are checked on their own
        const paints = (cs.backgroundColor !== 'rgba(0, 0, 0, 0)' && cs.backgroundColor !== 'transparent') ||
          cs.backgroundImage !== 'none' || cs.boxShadow !== 'none' ||
          parseFloat(cs.borderTopWidth) + parseFloat(cs.borderBottomWidth) + parseFloat(cs.borderLeftWidth) + parseFloat(cs.borderRightWidth) > 0 ||
          cs.overflowX !== 'visible' || cs.overflowY !== 'visible'
        const ownText = [...el.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim())
        if (!paints && !ownText && el.children.length && el.tagName.toLowerCase() !== 'svg') continue
        // Invisible through an ancestor's opacity counts as invisible
        let alpha = 1
        for (let p = el; p && p !== document.body && alpha > 0.02; p = p.parentElement) alpha *= +getComputedStyle(p).opacity
        if (alpha <= 0.02) continue
        const { n: k, name } = id(el)
        const pid = el.parentElement ? id(el.parentElement).n : -1
        const sib = el.nextElementSibling
        const next = sib && inFlow(el) && inFlow(sib) ? id(sib).n : -1
        items.push([k, name, r.left - box.left, r.top - box.top, r.width, r.height, pid, next])
      }
      V.frames.push({ t: performance.now() - t0, mark: V.mark, items })
    } catch (e) { V.errors.push(`recorder: ${e.message}`); return }
    requestAnimationFrame(tick)
  }
  requestAnimationFrame(tick)
}

// Pill state right after a click: the .vrail strip holding the clicked
// element, its pill's running left/width transitions, and .rail-noanim.
function pillProbe(sel) {
  const el = document.querySelector(sel)
  const strip = el && el.closest('.vrail')
  if (!strip) return null
  const pill = strip.querySelector(':scope > .v-pill')
  if (!pill) return { strip: strip.id || strip.className, pill: false }
  const anims = pill.getAnimations().filter((a) => a.playState === 'running')
  const props = anims.map((a) => a.transitionProperty || '').filter(Boolean)
  return { strip: strip.id ? `#${strip.id}` : '.' + strip.className.split(/\s+/)[0], pill: true, running: props, noanim: strip.classList.contains('rail-noanim') }
}

// ---- Analysis (Node side) --------------------------------------------------

function analyse(frames) {
  const at = frames.map((f) => new Map(f.items.map((i) => [i[0], i])))
  // A late frame carries several frames of gliding at once and can't tell a
  // snap from a glide, so frames around a stall are not judged
  const dts = frames.slice(1).map((fr, i) => fr.t - frames[i].t).sort((a, b) => a - b)
  const frameMs = dts[Math.floor(dts.length / 2)] || 16.7
  const late = (f) => f > 0 && frames[f].t - frames[f - 1].t > frameMs * 1.6
  const s = (ms) => (ms / 1000).toFixed(2)
  const where = (fr) => `${s(fr.t)}s${fr.mark ? ` [${fr.mark}]` : ''}`

  const found = new Map()
  for (let f = 2; f < frames.length - 1; f++) {
    if (late(f - 1) || late(f) || late(f + 1)) continue
    for (const [k, it] of at[f]) {
      const a = at[f - 2].get(k), b = at[f - 1].get(k), c = at[f + 1].get(k)
      if (!a || !b || !c) continue
      for (const [axis, ix] of [['x', 2], ['y', 3], ['width', 4], ['height', 5]]) {
        const d = it[ix] - b[ix]
        const calm = Math.max(Math.abs(b[ix] - a[ix]), Math.abs(c[ix] - it[ix]), 0.4)
        if (Math.abs(d) > 2 && Math.abs(d) > 3 * calm) {
          const key = `${k}:${axis}`
          const prev = found.get(key)
          if (prev) prev.count++
          else found.set(key, { id: k, parent: it[6], t: frames[f].t, fr: frames[f], name: it[1], axis, d, count: 1 })
        }
      }
    }
  }

  const born = new Map()
  frames.forEach((fr, f) => fr.items.forEach((i) => born.has(i[0]) || born.set(i[0], f)))
  const drift = new Map()
  for (let f = 1; f < frames.length; f++) {
    if (late(f)) continue
    for (const [k, it] of at[f]) {
      const nx = it[7] >= 0 ? at[f].get(it[7]) : null
      const pa = at[f - 1].get(k), pb = nx && at[f - 1].get(nx[0])
      if (!nx || !pa || !pb) continue
      if (f - born.get(k) < 45 || f - born.get(nx[0]) < 45) continue
      const held = Math.abs(it[5] - pa[5]) < 0.3 && Math.abs(nx[5] - pb[5]) < 0.3
      const dg = nx[3] - (it[3] + it[5]) - (pb[3] - (pa[3] + pa[5]))
      if (!held || Math.abs(dg) <= 1) continue
      const key = `${k}>${nx[0]}`
      const d = drift.get(key) ?? { fr: frames[f], a: it[1], b: nx[1], max: 0, count: 0 }
      d.max = Math.max(d.max, Math.abs(dg))
      d.count++
      drift.set(key, d)
    }
  }

  const anchored = new Map()
  for (let f = 1; f < frames.length; f++) {
    if (late(f)) continue
    for (const [k, it] of at[f]) {
      if (!/\.[\w-]*(menu|popover|sheet|dropdown)[\w-]*/i.test(it[1]) || f - born.get(k) < 30) continue
      const p = at[f - 1].get(k)
      if (!p) continue
      const dy = it[3] - p[3], dh = it[5] - p[5]
      if (Math.abs(dy) < 0.3 || Math.abs(dh) < 0.3) continue
      const a = anchored.get(k) ?? { fr: frames[f], name: it[1], y: 0, h: 0 }
      a.y += dy; a.h += dh
      anchored.set(k, a)
    }
  }

  // A parent's snap drags its children with it: report the outermost only
  const lines = [...found.values()].sort((p, q) => p.t - q.t)
  const kept = []
  for (const l of lines) {
    if (kept.some((o) => o.id === l.parent && Math.abs(o.t - l.t) < 40 && o.axis === l.axis && Math.abs(o.d - l.d) < 0.6)) continue
    kept.push(l)
  }
  return [
    ...[...anchored.values()].filter((a) => Math.abs(a.y) >= 1).map((a) => `anchor: ${a.name} moves ${a.y > 0 ? 'down' : 'up'} ${Math.abs(a.y).toFixed(1)}px while its height changes ${a.h.toFixed(0)}px (from ${where(a.fr)}); anchor it by its top`),
    ...[...drift.values()].filter((d) => d.count >= 4).map((d) => `drift: ${d.a} and ${d.b} glide out of step (gap moves up to ${d.max.toFixed(1)}px a frame, ${d.count} frames from ${where(d.fr)})`),
    ...kept.map((l) => `jump: ${l.name} ${l.axis} ${l.d > 0 ? '+' : ''}${l.d.toFixed(1)}px in one frame at ${where(l.fr)}${l.count > 1 ? `, ${l.count} times` : ''}`),
  ]
}

// ---- Run -------------------------------------------------------------------

const browser = await launch()
const viewport = opt.mobile ? { width: 375, height: 812 } : { width: opt.width, height: 900 }
const ctx = await browser.newContext({ viewport, ...(opt.mobile ? { isMobile: true, hasTouch: true, deviceScaleFactor: 2 } : {}) })
const page = await ctx.newPage()
const errors = []
page.on('pageerror', (e) => errors.push(`page: ${e.message}`))
// A fresh profile is bounced to login.html; take the app's own guest path
await page.addInitScript(() => { try { localStorage.setItem('vf-guest', '1') } catch {} })
if (opt.theme) await page.addInitScript((t) => { try { localStorage.setItem('snapdraft-theme', t); localStorage.setItem('vault-theme-v2', '1') } catch {} }, opt.theme)

const pills = []
let snap
try {
  await page.goto(url, { waitUntil: 'load', timeout: 45000 })
  if (opt.sleeper) {
    await page.fill('#sleeper-username', opt.sleeper)
    await page.evaluate(() => window.setupConnect())
    // Step 2 is the league picker: wait for it, then enter with the default
    // selection (all leagues)
    await page.waitForFunction(() => document.getElementById('setup')?.classList.contains('gone') || /pick the leagues/i.test(document.getElementById('setup')?.innerText || ''), null, { timeout: 45000 })
    await page.evaluate(() => { if (!document.getElementById('setup').classList.contains('gone')) window.vpEnterProfile() })
    await page.waitForFunction(() => { const el = document.getElementById('setup'); return !el || el.classList.contains('gone') }, null, { timeout: 60000 })
    // The overlay fades out after .gone lands; let it clear the pointer
    await page.waitForTimeout(800)
  }
  if (opt.wait) await page.waitForSelector(opt.wait, { timeout: 30000 })
  await page.waitForSelector(opt.select, { state: 'attached', timeout: 15000 })
  // Let first paint, webfonts and the initial pill placement settle before
  // recording, so load-time placement isn't reported as a jump
  await page.waitForTimeout(opt.settle)
  await page.evaluate(recorder, opt.select)
  await page.waitForTimeout(300)
  if (opt.click.length) {
    for (const sel of opt.click) {
      await page.evaluate((m) => { window.__mc.mark = m }, `click ${sel}`)
      await page.click(sel, { timeout: 10000 })
      await page.waitForTimeout(40)
      const p = await page.evaluate(pillProbe, sel)
      if (p) pills.push({ click: sel, ...p })
      await page.waitForTimeout(opt.gap)
    }
  } else {
    await page.waitForTimeout(opt.ms)
  }
} catch (e) { errors.push(e.message.split('\n')[0]) }
// Keep whatever was recorded before a failure
try { snap = await page.evaluate(() => { if (window.__mc) window.__mc.stopped = true; return window.__mc || null }) } catch {}
await browser.close()

const frames = snap?.frames || []
const findings = frames.length > 4 ? analyse(frames) : []
const pillFindings = pills.flatMap((p) => {
  if (!p.pill) return [`pill: ${p.click} sits in ${p.strip} but the strip has no .v-pill`]
  const moving = p.running.some((x) => /left|width/.test(x))
  const out = []
  if (p.noanim) out.push(`pill: ${p.strip} set .rail-noanim on ${p.click}, so the pill snapped instead of travelling`)
  if (!moving) out.push(`pill: ${p.strip} pill had no running left/width transition 40ms after ${p.click}`)
  return out
})
const all = [...pillFindings, ...findings]
const dts = frames.slice(1).map((fr, i) => fr.t - frames[i].t).sort((a, b) => a - b)
const medianMs = dts[Math.floor(dts.length / 2)] || 0

console.log(`motion-check: ${url} root=${opt.select} ${viewport.width}x${viewport.height}`)
console.log(`  ${frames.length} frames over ${frames.length ? (frames.at(-1).t / 1000).toFixed(1) : 0}s, median frame ${medianMs.toFixed(1)}ms, ${snap?.elements ?? 0} elements under root`)
if (medianMs > 34) console.log('  warning: slow frames make the jump check skip stalls; narrow --select to the strip or panel you are testing')
for (const p of pills) if (p.pill) console.log(`  pill ${p.click}: ${p.strip} running=[${p.running.join(',') || 'none'}] noanim=${p.noanim}`)
for (const line of all) console.log(`  ${line}`)
for (const e of [...errors, ...(snap?.errors || [])]) console.error(`  incomplete: ${e}`)
const status = errors.length || !frames.length ? 'incomplete' : all.length ? `${all.length} finding${all.length > 1 ? 's' : ''}` : 'clean'
console.log(`motion-check: ${status}; this checks geometry only, still watch the motion`)

if (opt.report) {
  const path = resolve(opt.report)
  mkdirSync(dirname(path), { recursive: true })
  writeFileSync(path, JSON.stringify({ url, select: opt.select, viewport, frames: frames.length, medianMs, pills, findings: all, errors }, null, 2) + '\n')
}
process.exitCode = errors.length || !frames.length ? 2 : all.length ? 1 : 0
