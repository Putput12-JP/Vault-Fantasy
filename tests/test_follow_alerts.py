import datetime as dt, json, os, sys, tempfile, unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nba", "scripts"))
import follow_alerts as A  # noqa: E402
import fast_poll as F  # noqa: E402

NOW = 1_800_000_000
TIP = NOW + 5 * 3600
M = {"m1": {"cid": "0xc1", "start": TIP, "type": "moneyline", "q": "Nuggets vs. Thunder", "outcomes": json.dumps(["Nuggets", "Thunder"]), "event": "nba-den-okc-2026-10-22"}}
RANK = {"0xP": {"tier": "proven", "post": 0.021, "p": 0.97, "raw": {"nba": [6, 0.02], "nfl": [22, 0.01]}},
        "0xW": {"tier": "watching", "post": 0.005, "p": 0.7, "raw": {}}, "0xB": {"tier": "probable", "post": 0.01, "p": 0.9, "raw": {"nfl": [5, 0.03]}}}


class St:
    def __init__(self, root):
        self.root = root; self.rank = RANK; self.sent = {}


def row(w="0xP", t=NOW - 60, o=1, usd=7400, px=0.74, who="Corrupt-Poisoning"):
    return {"t": t, "s": "pm", "k": "m1", "o": o, "usd": usd, "px": px, "w": w, "who": who, "id": f"{w}{t}{o}"}


class Alerts(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.root, "snapshots", dt.datetime.fromtimestamp(NOW, A.ET).date().isoformat()))
        os.environ["DISCORD_WEBHOOK_URL"] = "https://example.invalid/hook"
        self.out = []
        self.post = lambda url, embeds: self.out.append(embeds) or True

    def tearDown(self):
        os.environ.pop("DISCORD_WEBHOOK_URL", None)

    def test_ranked_ticket_alerts_once_with_price_and_follow_line(self):
        st = St(self.root)
        n = A.notify(st, [row()], M, {"m1": [0.26, 0.27, 0.26]}, NOW, self.post)
        self.assertEqual(n, 1)
        e = self.out[0][0]
        self.assertIn("Proven wallet Corrupt-Poisoning bought Thunder to win", e["title"])
        self.assertIn("$7,400", e["description"]); self.assertIn("74c", e["description"]); self.assertIn("Ask 74c matches", e["description"])   # thunder ask = 1 - 0.25
        self.assertIn("Context, not a bet", e["footer"]["text"])
        self.assertEqual(A.notify(st, [row()], M, {"m1": [0.26, 0.27, 0.26]}, NOW + 60, self.post), 0)     # same wallet, market, outcome: never twice
        st2 = St(self.root); st2.sent = None                                                                        # a restarted recorder reads alerts.json
        self.assertEqual(A.notify(st2, [row()], M, {}, NOW + 120, self.post), 0)
        self.assertEqual(len(self.out), 1)

    def test_filters(self):
        st = St(self.root)
        rows = [row(w="0xW"), row(w="0xNone"), row(t=NOW - 3600, w="0xB"), row(t=TIP + 5, w="0xB")]      # watching, unranked, stale, after tip
        self.assertEqual(A.notify(st, rows, M, {}, NOW, self.post), 0)
        os.environ.pop("DISCORD_WEBHOOK_URL")
        self.assertEqual(A.notify(St(self.root), [row()], M, {}, NOW, self.post), 0)                     # no webhook: silent no-op

    def test_failed_post_retries_and_other_side_note_and_sanitising(self):
        st = St(self.root)
        self.assertEqual(A.notify(st, [row(who="@everyone **x**")], M, {}, NOW, lambda u, e: False), 0)
        self.assertEqual(len(st.pending), 1)
        self.assertEqual(A.notify(st, [], M, {}, NOW + 60, self.post), 1)               # retried next cycle
        e = self.out[-1][0]
        self.assertNotIn("@", e["title"]); self.assertNotIn("*", e["title"])
        A.notify(st, [row(o=0, t=NOW + 30)], M, {}, NOW + 61, self.post)
        self.assertIn("also bought the other side", self.out[-1][0]["description"])
        self.assertEqual(json.loads(json.dumps({"allowed_mentions": {"parse": []}}))["allowed_mentions"], {"parse": []})

    def test_batches_ten_embeds_per_message(self):
        st = St(self.root)
        rows = [row(w=f"0xB{i}", t=NOW - 30 - i) for i in range(12)]
        for i in range(12):
            RANK[f"0xB{i}"] = RANK["0xB"]
        self.assertEqual(A.notify(st, rows, M, {}, NOW, self.post), 12)
        self.assertEqual([len(x) for x in self.out], [10, 2])

    def test_fast_poll_does_not_alert_the_first_backlog_cycle(self):
        calls = []
        orig = A.notify
        A.notify = lambda *a, **k: calls.append(1) or 0
        try:
            root = tempfile.mkdtemp()
            day = os.path.join(root, "snapshots", dt.datetime.fromtimestamp(NOW, F.ET).date().isoformat()); os.makedirs(day)
            with open(os.path.join(day, "meta.jsonl"), "w") as f:
                f.write(json.dumps({"k": "m1", "src": "polymarket", "event": "e", "type": "moneyline", "start": TIP, "cid": "0xc1"}) + "\n")
            tr = [{"timestamp": NOW - 30, "side": "BUY", "outcomeIndex": 0, "price": 0.5, "size": 4000, "proxyWallet": "0xP", "conditionId": "0xc1", "transactionHash": "0xabc0123456789abcdef", "pseudonym": "x"}]
            get = lambda url: [{"id": "m1", "bestBid": "0.49", "bestAsk": "0.51", "lastTradePrice": "0.5", "closed": False}] if "gamma" in url else (tr if "offset=0" in url else [])
            st = F.State(root, NOW)
            F.cycle(st, NOW, get)
            self.assertEqual(calls, [])                      # first cycle: backlog
            tr.append(dict(tr[0], timestamp=NOW + 40, transactionHash="0xdef0123456789abcdef"))
            F.cycle(st, NOW + 60, get)
            self.assertEqual(calls, [1])
        finally:
            A.notify = orig


if __name__ == "__main__":
    unittest.main()
