import json, os, sys, tempfile, unittest, datetime as dt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "nba", "scripts"))
import wallet_bets as WB  # noqa: E402

TIP = 1792700000
NOW = TIP + 6 * 3600


def write(d, name, rows):
    with open(os.path.join(d, name), "w") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")


def pm(k, typ, line, outs, ev="nba-cle-phi-2026-10-22"):
    return {"k": k, "src": "polymarket", "event": ev, "type": typ, "line": line, "outcomes": json.dumps(outs), "start": TIP}


def fill(i, w, k, o, usd, px=0.5, t=TIP - 3600):
    return {"t": t + i, "s": "pm", "k": k, "o": o, "usd": usd, "px": px, "w": w, "id": f"f{i}"}


def build(tape, score=None, extra_meta=()):
    root = tempfile.mkdtemp()
    day = os.path.join(root, "snapshots", dt.datetime.fromtimestamp(NOW, WB.day_dirs.__globals__["ET"]).date().isoformat())
    os.makedirs(day)
    os.makedirs(os.path.join(root, "results"))
    write(day, "meta.jsonl", [pm("ml", "moneyline", None, ["Cavaliers", "76ers"]), pm("sp", "spreads", -2.5, ["76ers", "Cavaliers"]), pm("tot", "totals", 222.5, ["Over", "Under"]),
                              {"k": "401|100|game", "src": "espn", "game": "401", "away": "CLE", "home": "PHI", "tip": TIP}, *extra_meta])
    write(day, "tape.jsonl", tape)
    if score:
        json.dump({"score": score}, open(os.path.join(root, "results", "401.meta.json"), "w"))
    return root


class WalletBets(unittest.TestCase):
    def test_settle_all_three_markets_away_first(self):
        # CLE (away) 100, PHI (home) 110: PHI wins, PHI -2.5 covers (110-2.5 > 100), total 210 is under 222.5
        root = build([fill(1, "0xA", "ml", 0, 100), fill(2, "0xA", "sp", 0, 100), fill(3, "0xA", "tot", 1, 100)], {"CLE": 100, "PHI": 110})
        S = WB.update(root, NOW, {"0xA"})
        self.assertEqual(WB.settle(root, S, "ml", 0), -1)       # Cavaliers (away) lost
        self.assertEqual(WB.settle(root, S, "ml", 1), 1)        # 76ers won
        self.assertEqual(WB.settle(root, S, "sp", 0), 1)        # 76ers -2.5, won by 10
        self.assertEqual(WB.settle(root, S, "sp", 1), -1)       # Cavaliers +2.5 lost
        self.assertEqual(WB.settle(root, S, "tot", 0), -1)      # over
        self.assertEqual(WB.settle(root, S, "tot", 1), 1)       # under
        S["m"]["tot"][2] = 210                                  # exactly on the number is a push
        self.assertEqual(WB.settle(root, S, "tot", 0), 0)

    def test_no_final_score_is_not_settled(self):
        root = build([fill(1, "0xA", "ml", 0, 100)])
        S = WB.update(root, NOW, {"0xA"})
        self.assertIsNone(WB.settle(root, S, "ml", 0))
        out, _ = WB.summarize(root, S)
        self.assertEqual(out["0xA"]["open"], 1)
        self.assertEqual(out["0xA"]["rec"][0], 0)

    def test_two_games_for_one_pair_are_told_apart_by_tip(self):
        later = {"k": "402|100|game", "src": "espn", "game": "402", "away": "CLE", "home": "PHI", "tip": TIP + 30 * 86400}
        root = build([fill(1, "0xA", "ml", 0, 100)], {"CLE": 100, "PHI": 110}, [later])
        json.dump({"score": {"CLE": 120, "PHI": 90}}, open(os.path.join(root, "results", "402.meta.json"), "w"))
        S = WB.update(root, NOW, {"0xA"})
        self.assertEqual(WB.settle(root, S, "ml", 0), -1)       # the game that tipped at TIP, not the later one

    def test_normal_buckets_hedge_and_pool(self):
        # five solo bets of $100 and one $400 on moneylines of five different markets, plus a hedge that must not count
        metas, tape = [], []
        for n in range(6):
            metas.append(pm(f"m{n}", "moneyline", None, ["Cavaliers", "76ers"], ev=f"nba-cle-phi-2026-10-22"))
            tape.append(fill(n, "0xA", f"m{n}", 1, 400 if n == 5 else 100, 0.5))      # 76ers (home) every time: all win
        metas.append(pm("h", "moneyline", None, ["Cavaliers", "76ers"]))
        tape += [fill(20, "0xA", "h", 0, 1000), fill(21, "0xA", "h", 1, 1000)]
        root = build(tape, {"CLE": 100, "PHI": 110}, metas)
        S = WB.update(root, NOW, {"0xA"})
        out, pool = WB.summarize(root, S)
        a = out["0xA"]
        self.assertEqual(a["n"], 6)                              # the hedged market is out of normal and of the record
        self.assertEqual(a["norm"], 100)
        self.assertEqual(a["rec"][:3], [6, 6, 0])
        self.assertEqual(a["rec"][3], 900)                       # 5 x 100 + 400 staked
        self.assertEqual(a["rec"][4], 900)                       # a win at 50c doubles the stake
        self.assertEqual(a["bk"][1][:2], [5, 5])                 # about normal
        self.assertEqual(a["bk"][3][:2], [1, 1])                 # 4x normal
        self.assertEqual(pool["big"][0], 1)
        self.assertEqual(pool["rest"][0], 5)
        t = WB.ticket(out, "0xA", "m5", 1)
        self.assertEqual((t["res"], t["x"], t["tot"]), (1, 4.0, 400))

    def test_too_few_bets_has_no_normal_and_rebuild_keeps_larger_total(self):
        root = build([fill(1, "0xA", "ml", 0, 300), fill(2, "0xA", "ml", 0, 200)], {"CLE": 100, "PHI": 110})
        S = WB.update(root, NOW, {"0xA"})
        self.assertEqual(S["b"]["0xA|ml|0"][0], 500)
        out, _ = WB.summarize(root, S)
        self.assertIsNone(out["0xA"]["norm"])
        S2 = WB.update(root, NOW, {"0xA"})                       # same window again: no double counting
        self.assertEqual(S2["b"]["0xA|ml|0"][0], 500)
        S2["b"]["0xA|ml|0"][0] = 900                             # early fills that already left the window
        json.dump(S2, open(os.path.join(root, WB.FILE), "w"))
        self.assertEqual(WB.update(root, NOW, {"0xA"})["b"]["0xA|ml|0"][0], 900)


if __name__ == "__main__":
    unittest.main()
