#!/usr/bin/env python3
"""Install (or refresh) the proven-sharps side cards in both Sharp Money layouts. Idempotent: running it twice changes nothing.

Run it AFTER patch_v2.py: its anchors are the text patch_v2.py leaves behind. The card itself lives in sharp-money/side-cards.js
(window.VaultSideCards); this only wires it into the two shells, which are one page in two files:

  sharp-money/index.html (the hand-patched Halaska bundle)
    1. a <script> tag for side-cards.js
    2. the sidebar: Sharps in Reads, after Record
    3. the shell: the #sharps route, the page title and tip, the nav handler, the sport filter, the page width, the page itself,
       and a "Proven sharps" section on the Game page under the V2 sections
    4. the phone redirect lets #sharps through
  sharp-money/new/index.html (the phone layout)
    5. the same <script> tag, a Sharps chip beside Plays / Signals / Play record, the #sharps route, and the Game page section
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
SM = os.path.join(HERE, '..', '..', 'sharp-money')
n_changes = 0


def patch(path, subs):
    global n_changes
    s = open(path, encoding='utf-8').read()
    for old, new, label in subs:
        if new in s:
            continue
        assert s.count(old) == 1, '%s: anchor found %d times (the file changed)' % (label, s.count(old))
        s = s.replace(old, new)
        n_changes += 1
        print('patched', label)
    open(path, 'w', encoding='utf-8').write(s)


ce = 'U.createElement'
ico = ce + '(U.Fragment,null,' + ce + '("path",{d:"M4 20V10M10 20V4M16 20v-7M22 20H2"}))'
patch(os.path.join(SM, 'index.html'), [
    ('<script src="v2-pages.js?v=side1"></script>', '<script src="v2-pages.js?v=side1"></script>\n<script src="side-cards.js?v=1"></script>', 'classic: script tag'),
    ('["NFL Model","The Vault line against the sharp money"',
     '["Sharps","Who holds each side, and the proven wallets among them",' + ico + '],["NFL Model","The Vault line against the sharp money"', 'classic: nav Sharps'),
    ('if(location.hash==="#record")return{page:"record",key:null};',
     'if(location.hash==="#record")return{page:"record",key:null};if(location.hash==="#sharps")return{page:"sharps",key:null};', 'classic: router'),
    ('k.page==="record"?"Record":"Board"', 'k.page==="record"?"Record":k.page==="sharps"?"Sharps":"Board"', 'classic: page title'),
    ('Record:"Every rule and every V2 play, graded"}[smPg]',
     'Record:"Every rule and every V2 play, graded",Sharps:"Who holds each side on Polymarket. Context, with a suggested size from an untested rule"}[smPg]', 'classic: page tip'),
    ('O==="Record"?location.hash="record":P()', 'O==="Record"?location.hash="record":O==="Sharps"?location.hash="sharps":P()', 'classic: nav handler'),
    ('k.page==="plays"||k.page==="record")&&(0,a.jsx)(ve,{options:W', 'k.page==="plays"||k.page==="record"||k.page==="sharps")&&(0,a.jsx)(ve,{options:W', 'classic: sport filter'),
    ('k.page==="signals"||k.page==="record")&&smBW?1840:1280', 'k.page==="signals"||k.page==="record"||k.page==="sharps")&&smBW?1840:1280', 'classic: page width'),
    ('o&&k.page==="record"&&window.VaultV2&&(0,a.jsx)(window.VaultV2.Record,{D:o,sport:y.sport}),',
     'o&&k.page==="record"&&window.VaultV2&&(0,a.jsx)(window.VaultV2.Record,{D:o,sport:y.sport}),'
     'o&&k.page==="sharps"&&window.VaultSideCards&&(0,a.jsx)(window.VaultSideCards.Page,{sport:y.sport}),', 'classic: page'),
    ('children:(0,a.jsx)(window.VaultV2.GameTells,{D:o,g:(o.games||[]).find(H=>H.key===k.key)})}):null]}),',
     'children:(0,a.jsx)(window.VaultV2.GameTells,{D:o,g:(o.games||[]).find(H=>H.key===k.key)})}):null,'
     'window.VaultSideCards&&k.key?(0,a.jsx)("div",{style:{marginTop:16,maxWidth:620},children:(0,a.jsx)(window.VaultSideCards.Game,{gameKey:k.key})}):null]}),', 'classic: game page section'),
    ("!/^#(plays|signals|record)/.test(location.hash)", "!/^#(plays|signals|record|sharps)/.test(location.hash)", 'classic: phone redirect'),
])
patch(os.path.join(SM, 'new', 'index.html'), [
    ('<script src="../v2-pages.js?v=side1"></script>', '<script src="../v2-pages.js?v=side1"></script>\n<script src="../side-cards.js?v=1"></script>', 'new: script tag'),
    ("[['plays','Plays'],['signals','Signals'],['vrecord','Play record']]", "[['plays','Plays'],['signals','Signals'],['vrecord','Play record'],['sharps','Sharps']]", 'new: Sharps chip'),
    (" else if(r.startsWith('game/')){html=gamePage(decodeURIComponent(r.slice(5)));tab='board'}",
     " else if(r==='sharps'){tab='plays';html=head('Sharps','Who holds each side on Polymarket. Context, with a suggested size from an untested rule')+v2nav('sharps')+'<div data-side-cards></div>'}\n"
     " else if(r.startsWith('game/')){const gk=decodeURIComponent(r.slice(5));html=gamePage(gk)+(GM[gk]?'<div data-side-card=\"'+gk.replace(/\"/g,'&quot;')+'\"></div>':'');tab='board'}", 'new: routes'),
    (" if(window.VaultLineChart)VaultLineChart.scan(sc,k=>GM[k]);",
     " if(window.VaultLineChart)VaultLineChart.scan(sc,k=>GM[k]);\n"
     " if(window.VaultSideCards){const so={skin:'new',logo:(c,n)=>{const g=GM[c.vault&&c.vault.key];if(!g)return null;const t=[g.away,g.home].find(x=>x&&(x.name===n||x.abbr===n||String(x.name||'').endsWith(' '+n)));return t?teamUrl(g.sport,t):null}};"
     "const sp=sc.querySelector('[data-side-cards]');if(sp)VaultSideCards.mountPage(sp,so);const sg=sc.querySelector('[data-side-card]');if(sg)VaultSideCards.mountGame(sg,sg.dataset.sideCard,so)}", 'new: mounts'),
])
print('done,', n_changes, 'change(s)')
