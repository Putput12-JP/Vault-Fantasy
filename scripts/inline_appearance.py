#!/usr/bin/env python3
"""Inline src/vault-appearance.js into the pages that carry it.

Sharp Money is a prebuilt bundle with no generator, so its copy lives in
sharp-money/index.html as <script id="vault-appearance">…</script> and is refreshed here.
Vault NBA is rendered by nba/scripts/render_app.py (it fills /*VAULT_APPEARANCE*/ itself).
Run after editing src/vault-appearance.js:  python3 scripts/inline_appearance.py && python3 nba/scripts/render_app.py
"""
import os, re, sys
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
src = open(os.path.join(ROOT, 'src', 'vault-appearance.js'), encoding='utf-8').read().replace('</script', '<\\/script')
page = os.path.join(ROOT, 'sharp-money', 'index.html')
html = open(page, encoding='utf-8').read()
pat = re.compile(r'(<script id="vault-appearance">).*?(</script>)', re.S)
if not pat.search(html):
    sys.exit('sharp-money/index.html has no <script id="vault-appearance"> block')
open(page, 'w', encoding='utf-8').write(pat.sub(lambda m: m.group(1) + src + m.group(2), html, count=1))
print('inlined src/vault-appearance.js into sharp-money/index.html')
