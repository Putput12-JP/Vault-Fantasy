#!/usr/bin/env python3
"""Build mocks/sharps-following/index.html: a mock of a "Following" page for Sharp Money, with real stored data inlined.

Inputs (stored files, nothing computed beyond sorting and formatting):
  --wallets   wallets.json (scripts/build_side_cards.py --wallets-out): every proven wallet's book and all of its open positions
  --live      live.json from pm-cards-live, only for each game's team codes
Context only (CLAUDE.md): the page shows who holds what. It never shows a suggested size and feeds no agree total.

usage: build.py --wallets FILE --live FILE
"""
import argparse, datetime as dt, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
CT = dt.timezone(dt.timedelta(hours=-6))          # Central Standard Time (November)
GROUPS = {"ml": "Moneyline", "spread": "Spread", "total": "Total"}


def ct(t, fmt):
    return dt.datetime.fromtimestamp(t, CT).strftime(fmt) if t else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wallets", required=True); ap.add_argument("--live", required=True)
    a = ap.parse_args()
    W = json.load(open(a.wallets))
    teams = {(c["ev"], c["gst"]): c.get("vault") or {} for c in json.load(open(a.live))["games"]}
    wallets, games = [], {}
    for sport, ws in W["sports"].items():
        for w, e in ws.items():
            n = e.get("name") or ""
            name = (w[:6] + "…" + w[-4:]) if not n or re.match(r"^0x[0-9a-fA-F]{20,}", n) else n[:22]
            d = e.get("dive") or {}
            pos = []
            for p in e["positions"]:
                k = (p["ev"], p["gst"])
                if k not in games:
                    v, slug = teams.get(k, {}), re.match(r"^[a-z]+-([a-z0-9]+)-([a-z0-9]+)-\d{4}", p["ev"])   # slug: away, then home
                    games[k] = {"id": len(games), "sport": sport, "gst": p["gst"], "away": v.get("away") or (slug and slug.group(1).upper()),
                                "home": v.get("home") or (slug and slug.group(2).upper()), "when": ct(p["gst"], "%a %-I:%M %p CT")}
                pos.append({"gm": games[k]["id"], "g": p["g"], "side": p["side"], "line": p["line"], "usd": p["usd"], "px": p["px"],
                            "press": p["press"], "since": ct(p["since"], "%b %-d, %-I:%M %p"), "two": p["two_way"]})
            wallets.append({"w": w, "sport": sport, "name": name, "wl": [e["w_"], e["l_"]], "roi": e["roi"], "n": e["n"],
                            "usual": e["usual"], "pnl": e["pnl"], "clv": [e["clv"]["beat"], e["clv"]["n"]],
                            "lane": {k: (v[:3] if v else None) for k, v in (d.get("lane") or {}).items()},
                            "fav": d["fav"][:3] if d.get("fav") else None, "dog": d["dog"][:3] if d.get("dog") else None,
                            "size": {k: (v[:3] if v else None) for k, v in (d.get("size") or {}).items()}, "pos": pos})
    gl = sorted(games.values(), key=lambda g: g["gst"])
    data = {"built": ct(W["built"], "%b %-d, %-I:%M %p CT"), "groups": GROUPS, "wallets": wallets, "games": gl}
    tpl = open(os.path.join(HERE, "template.html")).read()
    open(os.path.join(HERE, "index.html"), "w").write(tpl.replace("/*DATA*/null", json.dumps(data, separators=(",", ":")).replace("</", "<\\/")))
    print(len(wallets), "proven wallets,", len(gl), "games,", sum(len(w["pos"]) for w in wallets), "open positions")


if __name__ == "__main__":
    main()
