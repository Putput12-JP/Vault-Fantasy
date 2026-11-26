#!/usr/bin/env python3
"""Structure-only accessibility fixes for the desktop Sharp Money shell (sharp-money/index.html). Idempotent.

index.html is a hand-patched bundle (its JSX source is not in the repo), so this works on the text, like
patch_v2.py and patch_control_room.py. Nothing here changes how the page looks; every fix is invisible
except the skip link, which only appears while it has keyboard focus.

  1. <html lang="en"> (the file had no <html> tag, so screen readers had no page language). No doctype on
     purpose: the page has always rendered in quirks mode, and a doctype switches it to standards mode,
     which re-flows line boxes around icons and inline blocks (pages grew 59 to 370px taller at 1400px in
     the pixel diff). Adding one needs its own layout pass.
  2. the page title in the header ("Plays", "Signals", ...) renders as an h1 with the same type and spacing
  3. the content column is a <main> landmark (id sm-main)
  4. a "Skip to content" link, first in the tab order, that moves focus to the main column without
     touching the hash route; it uses the shell's existing 2px accent focus ring

The phone shell (sharp-money/new/index.html) is plain source and carries the same fixes directly.
Re-run this after any change to index.html from another branch.
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


# 1. language (an explicit <html> start tag, still no doctype: see the note above)
if not s.lstrip().lower().startswith('<html'):
    assert not s.lstrip().lower().startswith('<!doctype'), 'unexpected doctype: re-check the quirks-mode note'
    s = '<html lang="en">\n' + s
    n_changes += 1
    print('patched lang')

# 2. header page title -> h1, same size, weight, colour and spacing (M renders `as`, margin reset)
sub('(0,a.jsx)(M,{size:"lg",weight:"semibold",children:smPg})',
    '(0,a.jsx)(M,{as:"h1",size:"lg",weight:"semibold",style:{margin:0},children:smPg})',
    'page title h1')

# 3. main landmark on the content column
sub('(0,a.jsxs)("div",{className:"sm-main",children:[',
    '(0,a.jsxs)("main",{className:"sm-main",id:"sm-main",children:[',
    'main landmark')

# 4. skip link, first child of the shell so it inherits the --sm-* colours
sub('children:[(0,a.jsx)(SmSide,',
    'children:[(0,a.jsx)("a",{className:"sm-skip",href:"#sm-main",children:"Skip to content"}),(0,a.jsx)(SmSide,',
    'skip link')

CSS = ('/* Skip link (a11y): hidden until it has keyboard focus, then a small chip at the top left with the shell focus ring. '
       'The main column only takes focus for the skip, so it gets no ring of its own. */\n'
       '.sm-skip{position:absolute;width:1px;height:1px;margin:-1px;padding:0;overflow:hidden;clip:rect(0 0 0 0);clip-path:inset(50%);white-space:nowrap;border:0}\n'
       '.sm-skip:focus{position:fixed;left:12px;top:12px;z-index:100;width:auto;height:auto;margin:0;padding:8px 14px;overflow:visible;clip:auto;clip-path:none;'
       'border:1px solid var(--sm-bd);border-radius:8px;background:var(--sm-pop);color:var(--sm-fg);font:500 13px/1.4 "Geist",system-ui,sans-serif;text-decoration:none;box-shadow:0 6px 18px rgba(0,0,0,.35)}\n'
       '.sm-skip:focus-visible{outline:2px solid var(--sm-acc);outline-offset:1px}\n'
       '#sm-main:focus{outline:none}\n')
sub('.sm-main{min-width:0}\n', '.sm-main{min-width:0}\n' + CSS, 'skip link css')

# the title used to be a span; keep the phone-width no-wrap rule on it
sub('.sm-bar>div:first-of-type span{white-space:nowrap}',
    '.sm-bar>div:first-of-type span,.sm-bar>div:first-of-type h1{white-space:nowrap}',
    'title nowrap')

JS = ('<script>/* Skip link (a11y): focus the main column without changing the hash, which is the page route */'
      'document.addEventListener("click",function(e){var a=e.target.closest&&e.target.closest("a.sm-skip");if(!a)return;e.preventDefault();'
      'var m=document.getElementById("sm-main");if(!m)return;m.setAttribute("tabindex","-1");m.focus({preventScroll:true});'
      'm.addEventListener("blur",function(){m.removeAttribute("tabindex")},{once:true})});</script>\n')
sub('<div id="root"></div>\n', '<div id="root"></div>\n' + JS, 'skip link handler')

open(IDX, 'w', encoding='utf-8').write(s)
print('done,', n_changes, 'change(s)')
