#!/usr/bin/env python3
"""Install (or refresh) the Following page in both Sharp Money layouts. Idempotent: running it twice changes nothing.

Run it AFTER patch_side_cards.py: its anchors are the text that script leaves behind. The page itself lives in
sharp-money/following.js (window.VaultFollowing); this only wires it into the two shells, which are one page in two files:

  sharp-money/index.html (the hand-patched Halaska bundle)
    1. a <script> tag for following.js
    2. the sidebar: Following in Reads, after Sharps
    3. the shell: the #following route, the page title and tip, the nav handler, the sport filter, the page width and the page
    4. the phone redirect lets #following through, as it does #sharps
  sharp-money/new/index.html (the phone layout)
    5. the same <script> tag, a Following chip beside Sharps, the #following route and its mount
"""
import os
HERE = os.path.dirname(os.path.abspath(__file__))
SM = os.path.join(HERE, '..', '..', 'sharp-money')
V = '1'                                              # following.js cache key: bump it whenever that file changes
TIP = 'Open bets from the proven wallets you follow. Context only'
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
ico = ce + '(U.Fragment,null,' + ce + '("path",{d:"M6.5 3.5h11v17l-5.5-4-5.5 4z"}))'
patch(os.path.join(SM, 'index.html'), [
    ('<script src="side-cards.js?v=37"></script>', '<script src="side-cards.js?v=37"></script>\n<script src="following.js?v=%s"></script>' % V, 'classic: script tag'),
    ('["NFL Model","The Vault line against the sharp money"',
     '["Following","The proven wallets you follow, and every bet they have open",' + ico + '],["NFL Model","The Vault line against the sharp money"', 'classic: nav Following'),
    ('if(location.hash==="#sharps")return{page:"sharps",key:null};',
     'if(location.hash==="#sharps")return{page:"sharps",key:null};if(location.hash==="#following")return{page:"following",key:null};', 'classic: router'),
    ('k.page==="sharps"?"Sharps":"Board"', 'k.page==="sharps"?"Sharps":k.page==="following"?"Following":"Board"', 'classic: page title'),
    ('untested rule"}[smPg]', 'untested rule",Following:"%s"}[smPg]' % TIP, 'classic: page tip'),
    ('O==="Sharps"?location.hash="sharps":P()', 'O==="Sharps"?location.hash="sharps":O==="Following"?location.hash="following":P()', 'classic: nav handler'),
    ('k.page==="sharps")&&(0,a.jsx)(ve,{options:W', 'k.page==="sharps"||k.page==="following")&&(0,a.jsx)(ve,{options:W', 'classic: sport filter'),
    ('k.page==="sharps")&&smBW?1840:1280', 'k.page==="sharps"||k.page==="following")&&smBW?1840:1280', 'classic: page width'),
    ('o&&k.page==="sharps"&&window.VaultSideCards&&(0,a.jsx)(window.VaultSideCards.Page,{sport:y.sport}),',
     'o&&k.page==="sharps"&&window.VaultSideCards&&(0,a.jsx)(window.VaultSideCards.Page,{sport:y.sport}),'
     'o&&k.page==="following"&&window.VaultFollowing&&(0,a.jsx)(window.VaultFollowing.Page,{sport:y.sport}),', 'classic: page'),
    ('|sharps)/.test(location.hash)', '|sharps|following)/.test(location.hash)', 'classic: phone redirect'),
])
patch(os.path.join(SM, 'new', 'index.html'), [
    ('<script src="../side-cards.js?v=37"></script>', '<script src="../side-cards.js?v=37"></script>\n<script src="../following.js?v=%s"></script>' % V, 'new: script tag'),
    ("['sharps','Sharps']]", "['sharps','Sharps'],['following','Following']]", 'new: Following chip'),
    (" else if(r==='sharps'){", " else if(r==='following'){tab='plays';html=head('Following','%s')+v2nav('following')+'<div data-following></div>'}\n else if(r==='sharps'){" % TIP, 'new: route'),
    (" if(window.VaultLineChart)VaultLineChart.scan(sc,k=>GM[k]);",
     " if(window.VaultLineChart)VaultLineChart.scan(sc,k=>GM[k]);\n"
     " if(window.VaultFollowing){const fp=sc.querySelector('[data-following]');if(fp)VaultFollowing.mountPage(fp,{skin:'new'})}", 'new: mount'),
])
print('done,', n_changes, 'change(s)')
