import datetime as dt, json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nba", "scripts"))
import fast_poll as F  # noqa: E402
import follow_ledger as L  # noqa: E402

NOW = L.FREEZE_T + 4 * 3600
TIP = NOW + 3600


def make_root():
    root = tempfile.mkdtemp()
    day = os.path.join(root, "snapshots", dt.datetime.fromtimestamp(NOW, F.ET).date().isoformat())
    os.makedirs(day)
    with open(os.path.join(day, "meta.jsonl"), "w") as f:
        f.write(json.dumps({"k": "m1", "src": "polymarket", "event": "nba-a-b", "type": "moneyline", "line": None, "start": TIP, "cid": "0xc1"}) + "\n")
        f.write(json.dumps({"k": "p1", "src": "polymarket", "event": "nba-a-b", "type": "points", "start": TIP, "cid": "0xc2"}) + "\n")
    return root, day


def trade(ts, side="BUY", oi=0, price=0.5, size=4000, w="0xS", cid="0xc1", tx="0xabcdef0123456789zz"):
    return {"timestamp": ts, "side": side, "outcomeIndex": oi, "price": price, "size": size, "proxyWallet": w, "conditionId": cid,
            "transactionHash": tx, "pseudonym": "x"}


def fake(trades, bid=0.49):
    def get(url):
        if "gamma-api" in url:
            return [{"id": "m1", "bestBid": str(bid), "bestAsk": "0.51", "lastTradePrice": "0.5", "closed": False}]
        return trades if "offset=0" in url else []
    return get


class Fast(unittest.TestCase):
    def test_only_game_markets_and_row_format(self):
        root, day = make_root()
        self.assertEqual(set(F.markets([day], NOW)), {"m1"})
        sell = F.trade_row(trade(NOW, side="SELL", oi=0, price=0.4), "m1", NOW)
        self.assertEqual((sell["o"], sell["px"], sell["usd"]), (1, 0.6, round(0.4 * 4000)))   # selling outcome 0 = buying outcome 1 at 1 - price
        self.assertEqual(sell["id"], "0xabcdef0123456789:1:4000"); self.assertEqual(sell["f"], NOW)

    def test_cycle_writes_files_dedupes_and_change_only(self):
        root, day = make_root()
        st = F.State(root, NOW)
        tr = [trade(NOW - 30), trade(NOW - 40, size=300, tx="0xsmall")]
        p = F.cycle(st, NOW, fake(tr))
        self.assertEqual((p["q"], p["tr"], p["qok"], p["tok"]), (1, 1, True, True))      # the $150 ticket is below the floor
        self.assertIsNone(p["lat"])                                                      # first cycle is backlog: no honest delay
        p2 = F.cycle(st, NOW + 60, fake(tr + [trade(NOW + 20, tx="0xnewone0123456789zz")]))
        self.assertEqual(p2["tr"], 1); self.assertEqual(p2["lat"], 40)
        rows = lambda n: [json.loads(x) for x in open(os.path.join(day, n))]
        self.assertEqual(len(rows("tape_fast.jsonl")), 2); self.assertEqual(len(rows("fastpm.jsonl")), 1)   # same quote not rewritten
        self.assertNotIn("f", rows("tape_fast.jsonl")[0]); self.assertIn("f", rows("tape_fast.jsonl")[1])
        F.cycle(st, NOW + 120, fake(tr, bid=0.47))
        self.assertEqual(len(rows("fastpm.jsonl")), 2)

    def test_failed_quote_call_is_not_ok(self):
        root, day = make_root()
        st = F.State(root, NOW)
        get = lambda url: None if "gamma-api" in url else []
        self.assertFalse(F.cycle(st, NOW, get)["qok"])

    def test_ledger_uses_fast_files(self):
        root, day = make_root()
        T = NOW - 600
        W = {"sharp": {"0xS": "nba"}, "dull": set(), "generated": "2026-10-01T00:00:00+00:00"}
        row = {"t": T, "s": "pm", "k": "m1", "o": 0, "usd": 2000, "px": 0.5, "w": "0xS", "who": "x", "id": "a:0:1", "f": T + 20}
        with open(os.path.join(day, "tape_fast.jsonl"), "w") as f:
            f.write(json.dumps(row) + "\n")
        with open(os.path.join(day, "tape.jsonl"), "w") as f:
            f.write(json.dumps({k: v for k, v in row.items() if k != "f"}) + "\n")           # same ticket in the main tape too
        with open(os.path.join(day, "fastpm.jsonl"), "w") as f:
            f.write(json.dumps({"t": T + 130, "k": "m1", "v": [0.52, 0.53, 0.52]}) + "\n")
        with open(os.path.join(day, "fastpoll.jsonl"), "w") as f:
            f.write(json.dumps({"t": T + 130, "qok": True}) + "\n")
        self.assertEqual(L.run(root, NOW, W)["new"], 1)
        ev = list(json.load(open(os.path.join(day, L.FILE))).values())[0]
        self.assertEqual(ev["det"], 20); self.assertEqual(ev["f"]["tk2"], [0.53, 130])


if __name__ == "__main__":
    unittest.main()
