#!/usr/bin/env python3
"""Build mocks/sharps-following/index.html: a mock of a "Following" page for Sharp Money, with real stored data inlined.

Inputs (all stored files, nothing computed beyond sums and sorting):
  --cards     pm_cards folder from pm-holders-data (frozen cards: each proven wallet's book as of its latest card)
  --live      live.json from pm-cards-live (open positions on upcoming games)
  --universe  pm_ledger/universe/<date>.json from sharp-history (wallet display names)
Context only (CLAUDE.md): the page shows who holds what. It never shows a suggested size and feeds no agree total.

usage: build.py --cards DIR --live FILE --universe FILE
"""
import argparse, datetime as dt, glob, json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
CT = dt.timezone(dt.timedelta(hours=-6))          # Central Standard Time (November)
GROUPS = {"ml": "Moneyline", "spread": "Spread", "total": "Total"}


def name_of(w, uni):
    n = ((uni.get("wallets") or {}).get(w) or {}).get("name") or ""
    if not n or re.match(r"^0x[0-9a-fA-F]{20,}", n):
        return w[:6] + "…" + w[-4:]
    return n[:22]


def slim(x):
    d = x.get("dive") or {}
    return {"w": x["w"], "wl": [x.get("w_"), x.get("l_")], "roi": x.get("roi"), "n": x.get("n"), "usual": x.get("usual"),
            "pnl": x.get("pnl"), "clv": [(x.get("clv") or {}).get("beat"), (x.get("clv") or {}).get("n")],
            "lane": {k: (v[:3] if v else None) for k, v in (d.get("lane") or {}).items()},
            "fav": (d.get("fav") or [None])[:3] if d.get("fav") else None, "dog": d.get("dog")[:3] if d.get("dog") else None,
            "size": {k: (v[:3] if v else None) for k, v in (d.get("size") or {}).items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cards", required=True); ap.add_argument("--live", required=True); ap.add_argument("--universe", required=True)
    a = ap.parse_args()
    uni = json.load(open(a.universe))
    live = json.load(open(a.live))
    books = {}                                       # (sport, wallet) -> (cut, book): the wallet's book on its latest card
    def take(card):
        for m in (card.get("markets") or {}).values():
            for s in (m.get("sides") or {}).values():
                for x in (s.get("all") or {}).get("list") or []:
                    k = (card["sport"], x["w"])
                    if k not in books or card["cut"] >= books[k][0]:
                        books[k] = (card["cut"], slim(x))
    for p in glob.glob(os.path.join(a.cards, "*", "frozen", "*", "*.json")):
        take(json.load(open(p)))
    games = []
    for c in sorted(live["games"], key=lambda c: c["gst"]):
        take(c)
        pos = []
        for g, m in (c.get("markets") or {}).items():
            for side, s in (m.get("sides") or {}).items():
                for x in (s.get("all") or {}).get("list") or []:
                    pos.append({"w": x["w"], "g": g, "side": side, "usd": x.get("usd"), "press": x.get("press")})
        if not pos:
            continue
        v = c.get("vault") or {}
        t = dt.datetime.fromtimestamp(c["gst"], CT)
        slug = re.match(r"^[a-z]+-([a-z0-9]+)-([a-z0-9]+)-\d{4}", c["ev"])           # nfl-buf-kc-2026-11-22: away, then home
        games.append({"sport": c["sport"], "ev": c["ev"], "away": v.get("away") or (slug and slug.group(1).upper()),
                      "home": v.get("home") or (slug and slug.group(2).upper()),
                      "when": t.strftime("%a %-I:%M %p CT"), "pos": pos})
    wallets = []
    for (sport, w), (_, b) in books.items():
        wallets.append(dict(b, sport=sport, name=name_of(w, uni)))
    built = dt.datetime.fromtimestamp(live["built"], CT).strftime("%b %-d, %-I:%M %p CT")
    data = {"built": built, "groups": GROUPS, "wallets": wallets, "games": games}
    tpl = open(os.path.join(HERE, "template.html")).read()
    out = tpl.replace("/*DATA*/null", json.dumps(data, separators=(",", ":")).replace("</", "<\\/"))
    open(os.path.join(HERE, "index.html"), "w").write(out)
    print(len(wallets), "wallet books,", len(games), "games with open proven positions,", sum(len(g["pos"]) for g in games), "positions")


if __name__ == "__main__":
    main()
