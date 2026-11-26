#!/usr/bin/env python3
"""Install (or refresh) the Sharp Money Control Room in sharp-money/index.html. Idempotent.

index.html is a hand-patched bundle (its JSX source is not in the repo), so this works on the text,
like patch_v2.py. The page itself lives in sharp-money/control-room.js and control-room.css. This
only wires it into the shell:

  1. stylesheet and script tags
  2. VaultControlPage, a thin React mount (same pattern as VaultEdgePage)
  3. a System > Control Room sidebar entry
  4. hash route #control, the page title and tip, the nav handler, the wide page width, and the page itself

Re-run it after any change to index.html from another branch.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
IDX = sys.argv[sys.argv.index('--file') + 1] if '--file' in sys.argv else os.path.join(HERE, '..', '..', 'sharp-money', 'index.html')
s = open(IDX, encoding='utf-8').read()
n_changes = 0


def sub(old, new, label):
    global s, n_changes
    if new in s:
        return
    assert s.count(old) == 1, '%s: anchor found %d times (the bundle changed)' % (label, s.count(old))
    s = s.replace(old, new)
    n_changes += 1
    print('patched', label)

def sub_if_present(old, new, label):
    """Repair a previous insert without failing on an unpatched file."""
    global s, n_changes
    if new in s or s.count(old) == 0:
        return
    assert s.count(old) == 1, '%s: anchor found %d times (the bundle changed)' % (label, s.count(old))
    s = s.replace(old, new)
    n_changes += 1
    print('patched', label)


sub('<script src="v2-pages.js?v=rules2"></script>',
    '<script src="v2-pages.js?v=rules2"></script>\n<link rel="stylesheet" href="control-room.css?v=1">\n<script src="control-room.js?v=1"></script>',
    'script tags')

page = (
    '/*vcr:start*/\n'
    'function VaultControlPage({ D }) {\n'
    '  var ref = U.useRef(null);\n'
    '  U.useEffect(function () {\n'
    '    if (!window.VaultControlRoom || !ref.current) return;\n'
    '    if (!ref.current._cr) ref.current._cr = window.VaultControlRoom.mount(ref.current, { board: D });\n'
    '    else ref.current._cr.refresh({ board: D });\n'
    '  }, [D && D.ts]);\n'
    '  return U.createElement("div", { ref: ref });\n'
    '}\n'
    '/*vcr:end*/\n'
)
sub('function VaultEdgePage({ D }) {', page + 'function VaultEdgePage({ D }) {', 'VaultControlPage')

ce = 'U.createElement'
ico = (ce + '(U.Fragment,null,' +
       ce + '("rect",{x:3,y:3,width:7,height:7,rx:1}),' +
       ce + '("rect",{x:14,y:3,width:7,height:7,rx:1}),' +
       ce + '("rect",{x:3,y:14,width:7,height:7,rx:1}),' +
       ce + '("rect",{x:14,y:14,width:7,height:7,rx:1}))')
edge = '["Edge Board","Novig against Pinnacle, biggest +EV",U.createElement(U.Fragment,null,U.createElement("path",{d:"M3 17l6-6 4 4 8-8"}),U.createElement("path",{d:"M15 7h6v6"}))'
# System is a top-level SmNav section, sibling of Reads, not a third element inside it.
nav_ok = edge + ']]],["System",[["Control Room","What keeps the board and the feeds fresh",' + ico + ']]]];'
# A previous insert closed one too few brackets after Edge Board, nesting System under Reads.
nav_broken = edge + ']],["System",[["Control Room","What keeps the board and the feeds fresh",' + ico + ']]]]];'
sub_if_present(nav_broken, nav_ok, 'nav Control Room repair')
sub(edge + ']]]];', nav_ok, 'nav Control Room')

sub('if(location.hash==="#edge")return{page:"edge",key:null};',
    'if(location.hash==="#edge")return{page:"edge",key:null};if(location.hash==="#control")return{page:"control",key:null};',
    'router')

sub('k.page==="following"?"Sharp Accounts":"Board"',
    'k.page==="following"?"Sharp Accounts":k.page==="control"?"Control Room":"Board"',
    'page title')

sub('"Sharp Accounts":"Every bet the sharp accounts have open. Star one to follow it. Context only"}[smPg]',
    '"Sharp Accounts":"Every bet the sharp accounts have open. Star one to follow it. Context only","Control Room":"What keeps the board and the feeds fresh, and when each last ran"}[smPg]',
    'page tip')

sub('O==="Sharp Accounts"?location.hash="following":P()',
    'O==="Sharp Accounts"?location.hash="following":O==="Control Room"?location.hash="control":P()',
    'nav handler')

sub('k.page==="scoreboard"||k.page==="edge"||k.page==="plays"||k.page==="signals"||k.page==="record"||k.page==="sharps"||k.page==="following")&&smBW?1840:1280',
    'k.page==="scoreboard"||k.page==="edge"||k.page==="plays"||k.page==="signals"||k.page==="record"||k.page==="sharps"||k.page==="following"||k.page==="control")&&smBW?1840:1280',
    'page width')

sub('o&&k.page==="edge"&&(0,a.jsx)(VaultEdgePage,{D:o}),',
    'o&&k.page==="edge"&&(0,a.jsx)(VaultEdgePage,{D:o}),o&&k.page==="control"&&(0,a.jsx)(VaultControlPage,{D:o}),',
    'page mount')

open(IDX, 'w', encoding='utf-8').write(s)
print('done,', n_changes, 'change(s)')
