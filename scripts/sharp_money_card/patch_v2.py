#!/usr/bin/env python3
"""Install (or refresh) the V2 pages in the Halaska Sharp Money page, sharp-money/index.html. Idempotent: running it twice changes nothing.

index.html is a hand-patched bundle (its JSX source is not in the repo), so this works on the text, like patch_index.py. It does not copy V2 code in: the pages
live in sharp-money/v2-pages.js and the rules in sharp-money/v2/gates.js, both loaded as plain scripts. This only wires them into the shell:

  1. <script> tags for v2/gates.js and v2-pages.js, next to line-chart.js and edge-board.js
  2. window.__smKit(): the kit (React, theme, Text, Card, Badge, segmented control ...) the V2 pages draw with, defined where those names are in scope
  3. the sidebar: Plays at the top of Markets; Signals and Record in Reads
  4. the shell: hash routes #plays, #signals, #record, the page title and tip, the sport filter in the top bar for Plays and Record, the page width,
     and the three pages themselves; the Game page gets the V2 "Plays on this game" and "Who is behind" sections underneath
  5. the phone redirect to new/ lets V2 hashes through, so a phone opening #plays gets the V2 pages

Re-run it after any change to index.html from another branch (it is how a merge conflict with an edit elsewhere in that file is resolved: take their file, run this).
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
IDX = sys.argv[sys.argv.index('--file') + 1] if '--file' in sys.argv else os.path.join(HERE, '..', '..', 'sharp-money', 'index.html')
s = open(IDX, encoding='utf-8').read()
n_changes = 0


def sub(old, new, label):
    """Replace one anchor. Already patched (the new text is present) is a no-op; an anchor that moved fails loudly."""
    global s, n_changes
    if new in s:
        return
    assert s.count(old) == 1, '%s: anchor found %d times (the bundle changed)' % (label, s.count(old))
    s = s.replace(old, new)
    n_changes += 1
    print('patched', label)


# 1. scripts
sub('<script src="edge-board.js"></script>', '<script src="edge-board.js"></script>\n<script src="v2/gates.js"></script>\n<script src="v2-pages.js"></script>', 'script tags')

# 2. the kit, defined at module level right before the sidebar so every name is in scope
kit = ('window.__smKit=function(){return{U:U,V:V,z:z,T:T,M:M,K:K,oe:oe,se:se,ve:ve,at:at,je:je,co:co,Lp:Lp,_a:_a}};\n')
sub('function SmSide({pg,go,collapsed,toggle,hidden})', kit + 'function SmSide({pg,go,collapsed,toggle,hidden})', 'kit')

# 3. sidebar entries
ce = 'U.createElement'
ico_plays = ce + '(U.Fragment,null,' + ce + '("path",{d:"M22 11.08V12a10 10 0 1 1-5.93-9.14"}),' + ce + '("polyline",{points:"22 4 12 14.01 9 11.01"}))'
ico_sig = ce + '(U.Fragment,null,' + ce + '("path",{d:"M3 3v18h18"}),' + ce + '("path",{d:"M7 14l4-4 3 3 5-6"}))'
ico_rec = ce + '(U.Fragment,null,' + ce + '("rect",{x:5,y:3,width:14,height:18,rx:2}),' + ce + '("path",{d:"M9 8h6M9 12h6M9 16h4"}))'
sub('var SmNav=[["Markets",[["Board","Where the sharp side is"',
    'var SmNav=[["Markets",[["Plays","Prices that clear every gate",' + ico_plays + '],["Board","Where the sharp side is"', 'nav Plays')
sub('["NFL Model","The Vault line against the sharp money"',
    '["Signals","What each signal has actually done",' + ico_sig + '],["Record","Every rule and every play, graded",' + ico_rec + '],["NFL Model","The Vault line against the sharp money"', 'nav Signals, Record')

# 4. the shell
sub('if(location.hash==="#edge")return{page:"edge",key:null};',
    'if(location.hash==="#edge")return{page:"edge",key:null};if(location.hash==="#plays")return{page:"plays",key:null};if(location.hash==="#signals")return{page:"signals",key:null};if(location.hash==="#record")return{page:"record",key:null};', 'router')
sub('k.page==="edge"?"Edge Board":"Board"', 'k.page==="edge"?"Edge Board":k.page==="plays"?"Plays":k.page==="signals"?"Signals":k.page==="record"?"Record":"Board"', 'page title')
sub('"Edge Board":"Novig against Pinnacle, biggest +EV first"}[smPg]',
    '"Edge Board":"Novig against Pinnacle, biggest +EV first",Plays:"Prices that beat two independent fair prices, ranked by the worst-case edge",Signals:"What each signal has actually done against the price it was taken at",Record:"Every rule and every V2 play, graded"}[smPg]', 'page tip')
sub('O==="Edge Board"?location.hash="edge":P()', 'O==="Edge Board"?location.hash="edge":O==="Plays"?location.hash="plays":O==="Signals"?location.hash="signals":O==="Record"?location.hash="record":P()', 'nav handler')
sub('o&&(k.page==="board"||k.page==="accounts")&&(0,a.jsx)(ve,{options:W', 'o&&(k.page==="board"||k.page==="accounts"||k.page==="plays"||k.page==="record")&&(0,a.jsx)(ve,{options:W', 'sport filter')
sub('k.page==="scoreboard"||k.page==="edge")&&smBW?1840:1280', 'k.page==="scoreboard"||k.page==="edge"||k.page==="plays"||k.page==="signals"||k.page==="record")&&smBW?1840:1280', 'page width')
pages = ('o&&k.page==="plays"&&window.VaultV2&&(0,a.jsx)(window.VaultV2.Plays,{D:o,sport:y.sport,openGame:L,narrow:!smBW}),'
         'o&&k.page==="signals"&&window.VaultV2&&(0,a.jsx)(window.VaultV2.Signals,{D:o}),'
         'o&&k.page==="record"&&window.VaultV2&&(0,a.jsx)(window.VaultV2.Record,{D:o,sport:y.sport}),')
sub('o&&k.page==="edge"&&(0,a.jsx)(VaultEdgePage,{D:o}),', 'o&&k.page==="edge"&&(0,a.jsx)(VaultEdgePage,{D:o}),' + pages, 'pages')
game_old = 'o&&k.page==="game"&&(0,a.jsx)(If,{D:o,gameK:k.key,go:A,wide:!0,narrow:!smBW,width:R-(smWide?smC?72:248:0)}),'
game_new = ('o&&k.page==="game"&&(0,a.jsxs)(a.Fragment,{children:[(0,a.jsx)(If,{D:o,gameK:k.key,go:A,wide:!0,narrow:!smBW,width:R-(smWide?smC?72:248:0)}),'
            'window.VaultV2&&k.key?(0,a.jsx)("div",{style:{marginTop:8},children:(0,a.jsx)(window.VaultV2.GameTells,{D:o,g:(o.games||[]).find(H=>H.key===k.key)})}):null]}),')
sub(game_old, game_new, 'game page tells')

# 5. phones: V2 hashes stay on this page
sub("if(ph&&v!=='classic')location.replace", "if(ph&&v!=='classic'&&!/^#(plays|signals|record)/.test(location.hash))location.replace", 'phone redirect')

# 6. the old Props page measured CLV against the price that raised the call. Show the exchange close (clvX) when the ledger has it, and say what the old figure was.
clvx = ('clvXN:xs.filter(p0=>p0.clvX!=null).length,clvX:(()=>{let q=xs.filter(p0=>p0.clvX!=null);return q.length?q.reduce((t0,p0)=>t0+p0.clvX,0)/q.length:null})(),clvXPos:xs.filter(p0=>p0.clvX>0).length')
sub('clvPos:c.filter(p0=>p0.clv>0).length}})():rr.all||', 'clvPos:c.filter(p0=>p0.clv>0).length,' + clvx + '}})():rr.all||', 'props week CLV (all)')
sub('clvPos:c.filter(p0=>p0.clv>0).length}})():rr.big||', 'clvPos:c.filter(p0=>p0.clv>0).length,' + clvx + '}})():rr.big||', 'props week CLV (big)')
sub('["Avg closing-line value",sg(A0.clv),"price at the call vs the close",A0.clv>0?100:0],',
    '[A0.clvXN?"Avg closing-line value (exchange close)":"Avg closing-line value (old close)",sg(A0.clvXN?A0.clvX:A0.clv),A0.clvXN?"against Kalshi and Novig on "+A0.clvXN+" calls. The old "+sg(A0.clv)+" used the price that raised the call":"measured against the price that raised the call, so it repeats the edge claimed and is not a check",(A0.clvXN?A0.clvX:A0.clv)>0?100:0],', 'props CLV tile')
sub('["Beat the close",A0.clvN?`${A0.clvPos} of ${A0.clvN}`:"–",A0.clvN?Math.round(A0.clvPos/A0.clvN*100)+"% of plays":"no closes yet",A0.clvN?A0.clvPos/A0.clvN*100:null],',
    '["Beat the close",A0.clvXN?`${A0.clvXPos} of ${A0.clvXN}`:A0.clvN?`${A0.clvPos} of ${A0.clvN}`:"–",A0.clvXN?Math.round(A0.clvXPos/A0.clvXN*100)+"% of plays (exchange close)":A0.clvN?Math.round(A0.clvPos/A0.clvN*100)+"% of plays (old close)":"no closes yet",A0.clvXN?A0.clvXPos/A0.clvXN*100:A0.clvN?A0.clvPos/A0.clvN*100:null],', 'props beat-the-close tile')
sub('["Big plays",bg.n||0,bg.clvN?`CLV ${sg(bg.clv)} · ${bg.clvPos} beat close`:"no closes yet",bg.clvN?bg.clvPos/bg.clvN*100:null],',
    '["Big plays",bg.n||0,bg.clvXN?`CLV ${sg(bg.clvX)} · ${bg.clvXPos} of ${bg.clvXN} beat the exchange close`:bg.clvN?`CLV ${sg(bg.clv)} · ${bg.clvPos} beat close (old close)`:"no closes yet",bg.clvXN?bg.clvXPos/bg.clvXN*100:bg.clvN?bg.clvPos/bg.clvN*100:null],', 'props big plays tile')

open(IDX, 'w', encoding='utf-8').write(s)
print('done,', n_changes, 'change(s)')
