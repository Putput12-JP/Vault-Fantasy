#!/usr/bin/env python3
"""Build the standalone side-card mocks. Each output inlines its CSS, JS and the real sample (relative links break in standalone mocks).
Usage: python3 mocks/side-card/build.py"""
import json, os
D = os.path.dirname(os.path.abspath(__file__)); S = os.path.join(D, "src")
rd = lambda n: open(os.path.join(S, n), encoding="utf-8").read()
FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@500;600&display=swap">')
PAGES = {
    "sharp-money.html": ("sharp-money.css", "Proven sharps side card · Sharp Money",
                         "Game page card in Sharp Money's look. At desktop width it uses the classic page's palette; at phone width it uses the new/ layout. Every card is a real game from the live sample."),
    "nba.html": ("nba.css", "Proven sharps side card · Vault NBA",
                 "The same card in the NBA app's Graphite look, sized for the Follow Board. Every card is a real game from the live sample."),
}
sample = json.dumps(json.load(open(os.path.join(S, "sample.json"))), separators=(",", ":"))
for out, (skin, title, sub) in PAGES.items():
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
{FONTS}
<style>
{rd(skin)}
{rd("card.css")}
</style></head>
<body>
<div class="mk">
  <div class="mk-h"><div><h1>{title}</h1><p>{sub} Context only: no units, no pick.</p></div>
    <div class="vseg sm" id="theme" aria-label="Theme"><i class="v-pill"></i><button type="button" data-v="dark">Dark</button><button type="button" data-v="light">Light</button></div></div>
  <div class="mk-grid" id="grid"></div>
</div>
<script>window.SIDE_SAMPLE={sample};</script>
<script>
{rd("card.js")}
{rd("page.js")}
</script>
</body></html>
"""
    assert chr(8212) not in html, "em dash in " + out
    open(os.path.join(D, out), "w", encoding="utf-8").write(html)
    print(out, len(html))
