#!/usr/bin/env python3
"""
Vault trade-value card generator.

Feed it a trade (two sides + per-asset values) and it renders a branded,
Twitter-ready PNG (1200x675) matching Vault's login theme:
Archivo headings, JetBrains Mono labels, onyx bg, steel-blue accent, no green.

USAGE
  1) edit the TRADE dict below (or pass a JSON file as argv[1]) — you only need
     player NAMES and a format string; values auto-fill from the real model
  2) make sure the static server is running (port 4173) so /fonts/fonts.css resolves
  3) python3 marketing/trade-card/make_trade_card.py [trade.json]
     -> writes marketing/trade-card/out.png

Values come LIVE from FantasyCalc (api.fantasycalc.com — ~1M real Sleeper/MFL/
Fleaflicker trades), the same source Vault's getFCValue uses. The "format"
string selects the bucket: "Dynasty|Redraft · Superflex|1QB · N-team [· Half-PPR|
Standard]". Player names are fuzzy-matched (apostrophes, suffixes, punctuation
ignored); rookie picks accept "2026 1st (mid)" or FantasyCalc's "2026 Pick 1.06".
Subtotals + verdict (fair / who wins by %) are computed. Add "val": N to any
asset to override the model for that one asset. Responses cache 12h under
.fc_cache/ so repeat cards are instant and work offline.
"""
import json, os, subprocess, sys, html, base64, re, time, urllib.request

# Vault shield logo, embedded as a data URI so cards render standalone.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
try:
    with open(os.path.join(_ROOT, "vault-shield.svg"), "rb") as _f:
        SHIELD = "data:image/svg+xml;base64," + base64.b64encode(_f.read()).decode()
except OSError:
    SHIELD = ""

# ─────────────────────────────────────────────────────────────────────────────
# REAL TRADE MODEL  — values come from FantasyCalc's live API (the same source
# Vault's getFCValue uses: ~1M real Sleeper/MFL/Fleaflicker trades). Player AND
# rookie-pick values are format-aware. Responses are cached locally (12h) so
# repeated cards are instant and work offline.
# ─────────────────────────────────────────────────────────────────────────────
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".fc_cache")
CACHE_TTL = 12 * 3600
_SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?", re.I)
_ORD = {"1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5,
        "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}
_TIER = {"early": 2, "mid": 6, "late": 10}  # slot within round (12-team basis)


def fc_params(fmt):
    """Parse a friendly format string into FantasyCalc API params."""
    f = (fmt or "").lower()
    is_dyn = not ("redraft" in f or "redr" in f)
    sf = any(t in f for t in ("superflex", "sflex", "2qb", "sf")) and "1qb" not in f
    num_qbs = 2 if sf else 1
    m = re.search(r"(\d+)\s*[- ]?team", f)
    teams = int(m.group(1)) if m else 12
    ppr = 0.5 if "half" in f else (0 if ("standard" in f or "non-ppr" in f) else 1)
    return is_dyn, num_qbs, teams, ppr


def pretty_fmt(is_dyn, q, t, ppr):
    parts = ["Dynasty" if is_dyn else "Redraft",
             "Superflex" if q == 2 else "1QB",
             f"{t}-team"]
    if ppr != 1:
        parts.append("Half-PPR" if ppr == 0.5 else "Standard")
    return " · ".join(parts)


def nkey(s):
    s = (s or "").lower().replace(".", "").replace("'", "").replace("’", "")
    s = _SUFFIX.sub("", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def load_fc(is_dyn, q, t, ppr):
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = f"{'dyn' if is_dyn else 'rdr'}_{q}qb_{t}t_ppr{ppr}"
    path = os.path.join(CACHE_DIR, key + ".json")
    fresh = os.path.exists(path) and (time.time() - os.path.getmtime(path) < CACHE_TTL)
    if not fresh:
        url = ("https://api.fantasycalc.com/values/current?"
               f"isDynasty={'true' if is_dyn else 'false'}&numQbs={q}&numTeams={t}&ppr={ppr}")
        try:
            with urllib.request.urlopen(url, timeout=25) as r:
                open(path, "wb").write(r.read())
        except Exception as e:  # offline / API down → fall back to any cached copy
            if not os.path.exists(path):
                raise SystemExit(f"FantasyCalc fetch failed and no cache for {key}: {e}")
            print(f"  (using cached values for {key}; live fetch failed: {e})")
    return json.load(open(path))


def build_index(fc):
    idx = {}
    for x in fc:
        p = x.get("player", {})
        name = p.get("name", "")
        is_pick = "pick" in name.lower() or "round" in name.lower()
        idx[nkey(name)] = {
            "name": name,
            "pos": "PICK" if is_pick else (p.get("position") or ""),
            "team": "" if is_pick else (p.get("maybeTeam") or ""),
            "val": int(round(x.get("value") or 0)),
        }
    return idx


def resolve_pick(name, idx, teams):
    """Map 'YYYY 1st (mid)' / 'YYYY Round 1' to a FantasyCalc pick entry."""
    f = name.lower()
    ym = re.search(r"(20\d\d)", f)
    rm = re.search(r"round\s*(\d)", f)
    rnd = int(rm.group(1)) if rm else next((v for k, v in _ORD.items() if k in f), None)
    if not (ym and rnd):
        return None
    year = ym.group(1)
    tier = next((v for k, v in _TIER.items() if k in f), 6)
    slot = max(1, min(teams, round(tier / 12 * teams)))
    hit = idx.get(nkey(f"{year} pick {rnd}.{slot:02d}"))
    if hit:
        return hit
    cand = [v for k, v in idx.items() if k.startswith(f"{year} pick {rnd}")]
    if cand:
        cand.sort(key=lambda z: z["val"], reverse=True)
        return cand[len(cand) // 2]
    return None


def enrich(trade):
    """Fill val/pos/team/canonical-name for every asset from the real model.
    An explicit "val" on an asset is kept as a manual override."""
    is_dyn, q, t, ppr = fc_params(trade.get("format", ""))
    idx = build_index(load_fc(is_dyn, q, t, ppr))
    missing = []
    for sk in ("give", "get"):
        for a in trade[sk]["assets"]:
            if a.get("val"):
                a["pos"] = a.get("pos", "")
                continue
            hit = idx.get(nkey(a["name"])) or resolve_pick(a["name"], idx, t)
            if hit:
                a["val"] = hit["val"]
                a["pos"] = a.get("pos") or hit["pos"]
                a["team"] = a.get("team") or hit["team"]
                if hit["name"]:
                    a["name"] = hit["name"]  # canonical spelling
            else:
                a["val"], a["pos"] = 0, a.get("pos", "?")
                missing.append(a["name"])
    trade["format"] = pretty_fmt(is_dyn, q, t, ppr)
    return trade, missing

# ─────────────────────────────────────────────────────────────────────────────
# EDIT THIS  (or pass a JSON file with the same shape as argv[1])
# ─────────────────────────────────────────────────────────────────────────────
TRADE = {
    # format drives the FantasyCalc bucket AND the label on the card
    "format": "Dynasty · Superflex · 12-team",
    "give": {  # the side "you" send — just names; values auto-fill from the model
        "label": "You give",
        "assets": [
            {"name": "Ja'Marr Chase"},
            {"name": "2026 1st (mid)"},
        ],
    },
    "get": {  # the side "you" receive
        "label": "You get",
        "assets": [
            {"name": "Bijan Robinson"},
            {"name": "Drake London"},
        ],
    },
    # fair band: within this % is called a fair/even trade
    "fair_band_pct": 8,
    # tip: add "val": 1234 to any asset to override the model for that one asset
}

W, H = 1200, 675
OUT = os.path.join(os.path.dirname(__file__), "out.png")
TMP = os.path.join(os.path.dirname(__file__), "_render.html")
SERVER = "http://localhost:4173"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# position colors (Vault language) — RB de-greened to a neutral slate to honor
# the "no green" brand rule; the rest use the app's real position hues.
POS = {
    "QB": "#ff6680", "WR": "#7bd0ff", "TE": "#f5c842",
    "RB": "#b9d2ec", "PICK": "#868c9b", "DEF": "#868c9b", "K": "#868c9b",
}


def fmt(n):
    return f"{n:,}"


def rows(assets):
    out = []
    for a in assets:
        pos = a.get("pos", "").upper()
        color = POS.get(pos, "#868c9b")
        team = a.get("team", "")
        meta = " · ".join(x for x in [pos, team] if x)
        out.append(f"""
        <div class="row">
          <div class="chip" style="color:{color};border-color:{color}55">{html.escape(pos)}</div>
          <div class="rname">
            <div class="pn">{html.escape(a['name'])}</div>
            <div class="pm">{html.escape(meta)}</div>
          </div>
          <div class="pv">{fmt(a['val'])}</div>
        </div>""")
    return "".join(out)


def side(data, align):
    total = sum(a["val"] for a in data["assets"])
    return total, f"""
      <div class="col">
        <div class="collabel">{html.escape(data['label'])}</div>
        <div class="rows">{rows(data['assets'])}</div>
        <div class="subtotal"><span>Total value</span><b>{fmt(total)}</b></div>
      </div>"""


def verdict(give_total, get_total, band):
    diff = get_total - give_total
    base = max(give_total, get_total, 1)
    pct = round(abs(diff) / base * 100)
    if pct <= band:
        return ("FAIR", "Fair trade", f"Within market range · {pct}% apart", "#8fb4e0")
    winner = "You win" if diff > 0 else "They win"
    color = "#8fb4e0" if diff > 0 else "#e23a4e"
    return ("SKEW", winner, f"by {pct}% in real-market value", color)


def build(trade):
    give_total, give_html = side(trade["give"], "l")
    get_total, get_html = side(trade["get"], "r")
    tag, big, small, vcolor = verdict(give_total, get_total, trade.get("fair_band_pct", 8))
    fmt_line = html.escape(trade.get("format", ""))
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="/fonts/fonts.css">
<style>
  :root{{--text:#f3f4f7;--text2:#c9cdd6;--muted:#868c9b;--accent2:#8fb4e0;
    --s2:#161922;--border:rgba(255,255,255,.08);--border2:rgba(255,255,255,.12);
    --sans:'Archivo','Hanken Grotesk',system-ui,sans-serif;--mono:'JetBrains Mono',monospace;}}
  *{{margin:0;padding:0;box-sizing:border-box}}
  html,body{{width:{W}px;height:{H}px;overflow:hidden}}
  .card{{width:{W}px;height:{H}px;position:relative;font-family:var(--sans);color:var(--text);
    background:radial-gradient(100% 120% at 50% -10%, #182234 0%, #10131b 46%, #0b0c11 100%);
    padding:40px 48px 44px;display:flex;flex-direction:column;overflow:hidden}}
  .watermark{{position:absolute;left:50%;top:47%;transform:translate(-50%,-50%);
    width:190px;opacity:.05;pointer-events:none;z-index:0}}
  .head,.body,.verdict{{position:relative;z-index:1}}
  .head{{display:flex;align-items:center;justify-content:space-between;margin-bottom:22px}}
  .kicker{{font-family:var(--mono);font-size:15px;font-weight:700;letter-spacing:.18em;
    text-transform:uppercase;color:var(--muted);display:flex;align-items:center;gap:11px}}
  .kicker .dot{{width:7px;height:7px;border-radius:50%;background:var(--accent2)}}
  .fmt{{font-family:var(--mono);font-size:13px;font-weight:500;letter-spacing:.1em;
    text-transform:uppercase;color:var(--muted)}}
  .body{{display:grid;grid-template-columns:1fr 66px 1fr;gap:0;flex:1;align-items:stretch}}
  .col{{background:rgba(255,255,255,.02);border:1px solid var(--border);border-radius:16px;
    padding:22px 24px;display:flex;flex-direction:column}}
  .collabel{{font-family:var(--mono);font-size:14px;font-weight:700;letter-spacing:.14em;
    text-transform:uppercase;color:var(--accent2);margin-bottom:16px}}
  .rows{{display:flex;flex-direction:column;gap:14px;flex:1}}
  .row{{display:flex;align-items:center;gap:14px}}
  .chip{{font-family:var(--mono);font-size:12px;font-weight:700;letter-spacing:.06em;
    border:1px solid;border-radius:7px;padding:5px 8px;min-width:52px;text-align:center}}
  .rname{{flex:1;min-width:0}}
  .pn{{font-family:var(--sans);font-weight:700;font-size:24px;letter-spacing:-.01em;
    white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
  .pm{{font-family:var(--mono);font-size:13px;font-weight:500;letter-spacing:.08em;
    text-transform:uppercase;color:var(--muted);margin-top:2px}}
  .pv{{font-family:var(--mono);font-weight:700;font-size:22px;font-variant-numeric:tabular-nums;color:var(--text)}}
  .subtotal{{display:flex;align-items:baseline;justify-content:space-between;margin-top:18px;
    padding-top:16px;border-top:1px solid var(--border)}}
  .subtotal span{{font-family:var(--mono);font-size:13px;font-weight:500;letter-spacing:.1em;
    text-transform:uppercase;color:var(--muted)}}
  .subtotal b{{font-family:var(--mono);font-weight:700;font-size:30px;font-variant-numeric:tabular-nums;color:var(--text)}}
  .vs{{display:flex;align-items:center;justify-content:center}}
  .vs span{{font-family:var(--sans);font-weight:900;font-size:20px;color:var(--muted);
    letter-spacing:.05em}}
  .verdict{{margin-top:22px;display:flex;align-items:center;justify-content:space-between;
    background:rgba(255,255,255,.02);border:1px solid var(--border);border-radius:14px;padding:18px 26px}}
  .vleft{{display:flex;flex-direction:column;gap:3px}}
  .vlabel{{font-family:var(--mono);font-size:13px;font-weight:700;letter-spacing:.16em;
    text-transform:uppercase;color:var(--muted)}}
  .vbig{{font-family:var(--sans);font-weight:800;font-size:30px;letter-spacing:-.02em}}
  .vbig b{{color:{vcolor}}}
  .vsmall{{font-family:var(--sans);font-size:16px;color:var(--text2)}}
  .vright{{display:flex;align-items:center;gap:13px}}
  .vlogo{{width:42px;height:auto;filter:drop-shadow(0 6px 16px rgba(0,0,0,.45))}}
  .vrtext{{text-align:right}}
  .wm{{font-family:var(--sans);font-weight:900;font-size:22px;letter-spacing:.04em}}
  .wmsub{{font-family:var(--mono);font-size:12px;font-weight:500;letter-spacing:.1em;
    text-transform:uppercase;color:var(--muted);margin-top:3px}}
</style></head>
<body><div class="card">
  <img class="watermark" src="{SHIELD}" alt="">
  <div class="head">
    <div class="kicker"><span class="dot"></span>Trade Check</div>
    <div class="fmt">{fmt_line}</div>
  </div>
  <div class="body">
    {give_html}
    <div class="vs"><span>VS</span></div>
    {get_html}
  </div>
  <div class="verdict">
    <div class="vleft">
      <div class="vlabel">Verdict</div>
      <div class="vbig"><b>{html.escape(big)}</b> <span class="vsmall">{html.escape(small)}</span></div>
    </div>
    <div class="vright">
      <img class="vlogo" src="{SHIELD}" alt="">
      <div class="vrtext">
        <div class="wm">VAULT</div>
        <div class="wmsub">vaultfantasy.com · Free</div>
      </div>
    </div>
  </div>
</div></body></html>"""


def main():
    trade = TRADE
    if len(sys.argv) > 1:
        with open(sys.argv[1]) as f:
            trade = json.load(f)
    trade, missing = enrich(trade)  # fill values from the real model
    if missing:
        print("  ⚠ not found in FantasyCalc (value=0):", ", ".join(missing))
    gt = sum(a["val"] for a in trade["give"]["assets"])
    rt = sum(a["val"] for a in trade["get"]["assets"])
    print(f"  {trade['format']}  |  give {gt:,}  vs  get {rt:,}")
    open(TMP, "w").write(build(trade))
    # copy into project root so the static server can serve it (fonts + relative)
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    served = os.path.join(root, "_tradecard.html")
    open(served, "w").write(build(trade))
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--force-device-scale-factor=1", f"--window-size={W},{H}",
                    f"--screenshot={OUT}", f"{SERVER}/_tradecard.html"],
                   stderr=subprocess.DEVNULL)
    try:
        os.remove(served)
    except OSError:
        pass
    print("wrote", OUT)


if __name__ == "__main__":
    main()
