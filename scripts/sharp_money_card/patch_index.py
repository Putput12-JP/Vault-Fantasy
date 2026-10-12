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
if cfb in s: s = s.replace(cfb, 'h(M,{size:"md",weight:"semibold"},h(VscMini,{g:S,side:"away",size:18}),S.away.abbr," @ ",h(VscMini,{g:S,side:"home",size:18}),S.home.abbr)')
row = 'x.away+" @ "+x.home),h("div",null,h(T,{size:"xs"},"Wk "'
if row in s: s = s.replace(row, '[h(VscId,{key:"a",id:x.away_id}),x.away," @ ",h(VscId,{key:"h",id:x.home_id}),x.home]),h("div",null,h(T,{size:"xs"},"Wk "')
hdr = 'weight:z.weight.bold}},x.away+" @ "+x.home),badge(x)'
if hdr in s: s = s.replace(hdr, 'weight:z.weight.bold,display:"flex",alignItems:"center",gap:8,flexWrap:"wrap"}},h(VscId,{id:x.away_id,size:30}),x.away,h("span",{style:{color:n.textTertiary,fontWeight:z.weight.regular}},"@"),h(VscId,{id:x.home_id,size:30}),x.home),badge(x)')
feed = '(0,a.jsx)(Ga,{onClick:()=>s(p.game),bold:!0,children:p.gameLbl})'
s = s.replace('VscPair,{g:i[p.game],lbl:p.gameLbl})', 'VscPair,{g:i[p.game],lbl:p.gameLbl,sport:p.sport})')
if feed in s: s = s.replace(feed, '(0,a.jsx)(Ga,{onClick:()=>s(p.game),bold:!0,children:(0,a.jsx)(VscPair,{g:i[p.game],lbl:p.gameLbl,sport:p.sport})})')
open(IDX, 'w', encoding='utf-8').write(s)
print('patched', os.path.getsize(IDX) // 1024, 'KB')
