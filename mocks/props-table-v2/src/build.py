#!/usr/bin/env python3
"""Inline base.css, lib.js and props.json into each template: the mocks open by double click with no sibling files."""
import json, os
H = os.path.dirname(os.path.abspath(__file__)); OUT = os.path.dirname(H)
base, lib, data = (open(os.path.join(H, f)).read() for f in ('base.css', 'lib.js', 'props.json'))
json.loads(data)
for name, out in (('a', 'a-scanner.html'), ('b', 'b-two-line.html'), ('c', 'c-split.html')):
    p = os.path.join(H, name + '.html')
    if not os.path.exists(p): continue
    s = open(p).read().replace('/*BASE_CSS*/', base).replace('/*LIB_JS*/', lib).replace('/*DATA*/', data.strip())
    open(os.path.join(OUT, out), 'w').write(s)
    print('wrote', out, len(s) // 1024, 'KB')
