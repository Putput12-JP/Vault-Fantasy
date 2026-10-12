#!/usr/bin/env python3
"""Install (or refresh) the share card in sharp-money/index.html. Idempotent: re-running replaces the vsc block in place.

index.html is a hand-patched bundle (its JSX source is not in the repo), so this works on the text:
  1. the card source (card.js + cfb_logos.json) goes between /*vsc:start*/ and /*vsc:end*/ ahead of function jp(
  2. jp's board branch renders <VaultEveryLine> instead of the old Every line table card
  3. the Board's centre column drops its own header, because the card carries the matchup and the sharp side
Run after editing card.js or after build_cfb_logos.py.
"""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
IDX = os.path.join(HERE, '..', '..', 'sharp-money', 'index.html')
s = open(IDX, encoding='utf-8').read()
card = open(os.path.join(HERE, 'card.js'), encoding='utf-8').read().replace('</script', '<\\/script')
logos = open(os.path.join(HERE, 'cfb_logos.json')).read()
card = card.replace('/*vsc-cfb*/{}/*end-vsc-cfb*/', '/*vsc-cfb*/' + logos + '/*end-vsc-cfb*/')
block = '/*vsc:start*/\n' + card + '\n/*vsc:end*/\n'

if '/*vsc:start*/' in s:
    s = re.sub(r'/\*vsc:start\*/.*?/\*vsc:end\*/\n', lambda m: block, s, flags=re.S)
else:
    assert s.count('function jp({g:e,noRead:t,tableOnly:n,mode:BM,compact:CP})') == 1, 'jp signature changed'
    s = s.replace('function jp({g:e,noRead:t,tableOnly:n,mode:BM,compact:CP})', block + 'function jp({g:e,noRead:t,tableOnly:n,mode:BM,compact:CP,row:BR})')
    a = 'return(0,a.jsxs)("div",{style:{display:"grid",gap:16},children:[(0,a.jsx)(K,{padding:16,children:(0,a.jsxs)(zt,{gap:12,children:[(0,a.jsx)(T,{size:"xs",mono:!0,style:{textTransform:"uppercase",letterSpacing:"0.1em"},children:"Every line"})'
    b = 'd(I)])})})]})}),(0,a.jsxs)("div",{style:{display:"grid",gridTemplateColumns:"repeat(auto-fit,minmax(260px,1fr))"'
    i = s.index(a); j = s.index(b, i)
    s = s[:i] + 'return(0,a.jsxs)("div",{style:{display:"grid",gap:16},children:[(0,a.jsx)(VaultEveryLine,{g:e,row:BR},e.key),' + s[j + len('d(I)])})})]})}),'):]
    call = 'h(jp,{g:cur,mode:"board",compact:NW})'
    assert s.count(call) == 1
    s = s.replace(call, 'h(jp,{g:cur,mode:"board",row:curRow,compact:NW})')
    k = s.index('h(jp,{g:cur,mode:"board"')
    hs = s.rindex('cur?h("div",{style:{display:"grid",gap:16}},', 0, k) + len('cur?h("div",{style:{display:"grid",gap:16}},')
    assert 'curRow.n+" independent signals agree' in s[hs:k]
    s = s[:hs] + '\n   ' + s[k:]
# 4. the Board slate: team logo instead of the colour dot
dot = 'h("i",{style:{width:8,height:8,borderRadius:"50%",background:c[R].color||n.textTertiary,display:"inline-block"}})'
if dot in s: s = s.replace(dot, 'h(VscMini,{g:c,side:R})')
# 5. every other place that shows a team: Game page header + picker, Top Reads cards, the other slate list, CFB model list
import re as _re
def _mini(m):
    call, v, side = m.group(1), m.group(2), m.group(3)
    size = 28 if call == 'hh(' else (22 if v == 'e' else 24)
    return '%sVscMini,{g:%s,side:"%s",size:%d})' % (call, v, side, size)
s = _re.sub(r'(hh\(|\(0,a\.jsx\)\()Ua,\{c:(\w+)\.(away|home)\.color\}\)', _mini, s)
dot2 = '(0,a.jsx)("i",{style:{width:8,height:8,borderRadius:"50%",background:c[R].color||s.textTertiary,display:"inline-block"}})'
if dot2 in s: s = s.replace(dot2, '(0,a.jsx)(VscMini,{g:c,side:R})')
cfb = 'h(M,{size:"md",weight:"semibold"},S.away.abbr," @ ",S.home.abbr)'
if cfb in s: s = s.replace(cfb, 'h(M,{size:"md",weight:"semibold"},U.createElement(VscMini,{g:S,side:"away",size:18}),S.away.abbr," @ ",U.createElement(VscMini,{g:S,side:"home",size:18}),S.home.abbr)')
# the same row exists in two components that alias createElement differently (h / hh), so never rely on the alias
s = s.replace('h(VscMini,{g:S,', 'U.createElement(VscMini,{g:S,').replace('UU.createElement', 'U.createElement')
row = 'x.away+" @ "+x.home),h("div",null,h(T,{size:"xs"},"Wk "'
if row in s: s = s.replace(row, '[h(VscId,{key:"a",id:x.away_id}),x.away," @ ",h(VscId,{key:"h",id:x.home_id}),x.home]),h("div",null,h(T,{size:"xs"},"Wk "')
hdr = 'weight:z.weight.bold}},x.away+" @ "+x.home),badge(x)'
if hdr in s: s = s.replace(hdr, 'weight:z.weight.bold,display:"flex",alignItems:"center",gap:8,flexWrap:"wrap"}},h(VscId,{id:x.away_id,size:30}),x.away,h("span",{style:{color:n.textTertiary,fontWeight:z.weight.regular}},"@"),h(VscId,{id:x.home_id,size:30}),x.home),badge(x)')
feed = '(0,a.jsx)(Ga,{onClick:()=>s(p.game),bold:!0,children:p.gameLbl})'
s = s.replace('VscPair,{g:i[p.game],lbl:p.gameLbl})', 'VscPair,{g:i[p.game],lbl:p.gameLbl,sport:p.sport})')
if feed in s: s = s.replace(feed, '(0,a.jsx)(Ga,{onClick:()=>s(p.game),bold:!0,children:(0,a.jsx)(VscPair,{g:i[p.game],lbl:p.gameLbl,sport:p.sport})})')

# 6. CFB Model page: the option B pick card replaces the plain header; every v2 (shadow) line on the page is removed
def _cut(s, start, end, keep_end=False, after=0):
    i = s.find(start)
    if i < 0: return s
    j = s.index(end, i + len(start))
    return s[:i] + s[(j if keep_end else j + len(end)):]
a = 'head=h("div",{style:{padding:NW?"14px":"16px 20px",borderBottom:`1px solid ${n.border}`,display:"grid",gap:10}},'
if a in s:
    s = _cut(s, a, ',\n  center=h("div",null,', keep_end=True)
    s = s.replace(',\n  center=h("div",null,', ',\n  center=h("div",null,', 1) if False else s
    i = s.index(',\n  center=h("div",null,')
    s = s[:i] + 'head=h(VaultCfbPick,{key:x.key,x:x,c:c,mk:mk,opp:opp,fm:fm,hl:hl,sn:Sn,dt:cfDt(x.kick),live:x.kick<now,pk:pk,back:NW?()=>setMv("list"):null,result:cover!=null?"Result: "+(cover>0?"covered":cover<0?"missed":"pushed")+" by "+Math.abs(cover).toFixed(1)+(x.clv==null?"":", "+te(x.clv)+" points against the closing line")+".":""})' + s[i:]
w = 'h("div",{style:{position:NW?"static":"sticky",top:0,zIndex:2,background:n.bg}},head),center)'
if w in s: s = s.replace(w, 'h("div",{style:{padding:NW?10:14}},head),center)')
# v2 (shadow) removals
s = s.replace('x.v2?gapRow("v2 (shadow)",x.v2.model_margin,"not shown as a pick"):null,', '')
if '\n   x.v2?h("div",{style:{padding:"14px 20px"}}' in s:
    i = s.index('\n   x.v2?h("div",{style:{padding:"14px 20px"}}'); j = s.index(':null);\n  detail=', i)
    s = s[:i].rstrip(',') + s[j + len(':null'):]
s = _cut(s, 'x.v2?(0,a.jsx)("div",{style:{padding:"6px 12px",borderTop:`1px solid ${n.borderSubtle}`},children:(0,a.jsx)(T,{size:"xs",children:`v2 (shadow):', '})}):null,')
s = _cut(s, 'd.v2_summary?h("div",{style:{padding:14,borderBottom:`1px solid ${n.borderSubtle}`,display:"grid",gap:4}},h(T,{size:"xs",mono:!0,style:lab},"Model v2 (shadow)")', '")):null,')
while 'd.v2_summary?(0,a.jsxs)(T,{size:"sm",children:[(0,a.jsx)("b",{children:"Model v2, tracked in the shadows: "})' in s:
    s = _cut(s, 'd.v2_summary?(0,a.jsxs)(T,{size:"sm",children:[(0,a.jsx)("b",{children:"Model v2, tracked in the shadows: "})', 'otherwise.`]}):null,')
open(IDX, 'w', encoding='utf-8').write(s)
print('patched', os.path.getsize(IDX) // 1024, 'KB')
