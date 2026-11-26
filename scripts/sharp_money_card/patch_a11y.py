#!/usr/bin/env python3
"""Structure-only accessibility fixes for the desktop Sharp Money shell (sharp-money/index.html). Idempotent.

index.html is a hand-patched bundle (its JSX source is not in the repo), so this works on the text, like
patch_v2.py and patch_control_room.py. Nothing here changes how the page looks; every fix is invisible.

  1. <html lang="en"> (the file had no <html> tag, so screen readers had no page language). No doctype on
     purpose: the page has always rendered in quirks mode, and a doctype switches it to standards mode,
     which re-flows line boxes around icons and inline blocks (pages grew 59 to 370px taller at 1400px in
     the pixel diff). Adding one needs its own layout pass.
  2. the page title in the header ("Plays", "Signals", ...) renders as an h1 with the same type and spacing
  3. the content column is a <main> landmark

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
    '(0,a.jsxs)("main",{className:"sm-main",children:[',
    'main landmark')

# the title used to be a span; keep the phone-width no-wrap rule on it
sub('.sm-bar>div:first-of-type span{white-space:nowrap}',
    '.sm-bar>div:first-of-type span,.sm-bar>div:first-of-type h1{white-space:nowrap}',
    'title nowrap')

open(IDX, 'w', encoding='utf-8').write(s)
print('done,', n_changes, 'change(s)')
