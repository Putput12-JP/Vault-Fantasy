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
open(IDX, 'w', encoding='utf-8').write(s)
print('patched', os.path.getsize(IDX) // 1024, 'KB')
