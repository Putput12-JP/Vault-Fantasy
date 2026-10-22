"""Publish the current NBA alternate-line prices from the SmartStake tape to the owner's Firestore, for the NBA page's Combo Check.

  python3 scripts/smartstake_publish_alts.py            # build and write once
  python3 scripts/smartstake_publish_alts.py --dry      # build and report only (nothing written)

SmartStake's API terms allow storing the data for internal research and require written permission to show it to users of our own
product. The prices therefore never go to GitHub or any public file. They go to Firestore collection `nbaAlts` in the Vault Fantasy
Firebase project, where firestore.rules lets only the owner's Google account read them; the page asks for the same Google login the rest
of Vault uses. The page credits SmartStake. (Owner's decision, 2026-10-20; see docs/smartstake-permission-request.md.)

CREDENTIALS: a Firebase service account key, saved by the owner as ~/.config/smartstake/firebase-sa.json (Firebase console, Project
settings, Service accounts, Generate new private key). It stays on this machine; never put it in the repo. The script signs a Google
OAuth token with it (openssl) and writes through the Firestore REST API, which bypasses the security rules by design.

One document per game: nbaAlts/<away>_<home>_<start>, fields {start, asof, credit, json}; `json` is the list of that game's props as a
JSON string (Firestore forbids arrays inside arrays). Pregame games starting within 36 hours only. Documents for games no longer in the
window are deleted on each run.

KILL SWITCH: create ~/.config/smartstake/publish.off (or set SMARTSTAKE_PUBLISH=0): the next run deletes every document. To stop for good
remove the nbaAlts block from firestore.rules and delete the collection in the console.
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smartstake_alts as A

AHEAD_H = 36
CONF = Path.home() / ".config" / "smartstake"
SA, OFF, LAST = CONF / "firebase-sa.json", CONF / "publish.off", CONF / "publish.last"
BT_LAST = CONF / "bankroll_bt.last"                               # mtime of the backtest record last written to Firestore
COLL = "nbaAlts"


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def access_token(sa):
    """A short-lived Google OAuth token for the service account: an RS256 JWT signed with openssl, exchanged at Google."""
    now = int(time.time())
    head = b64u(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claim = b64u(json.dumps({"iss": sa["client_email"], "scope": "https://www.googleapis.com/auth/datastore", "aud": "https://oauth2.googleapis.com/token",
                             "iat": now, "exp": now + 3000}).encode())
    unsigned = f"{head}.{claim}".encode()
    with tempfile.NamedTemporaryFile("w", suffix=".pem") as f:                 # 0600 by default, removed on close
        f.write(sa["private_key"])
        f.flush()
        sig = subprocess.run(["openssl", "dgst", "-sha256", "-sign", f.name], input=unsigned, capture_output=True, check=True).stdout
    body = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": f"{head}.{claim}.{b64u(sig)}"}).encode()
    with urllib.request.urlopen(urllib.request.Request("https://oauth2.googleapis.com/token", data=body), timeout=30) as r:
        return json.load(r)["access_token"]


def docs_for(props, asof):
    """{doc id: Firestore REST fields}: one document per game."""
    games = {}
    for p in props:
        games.setdefault((p["away"], p["home"], p["start"]), []).append({k: p[k] for k in ("n", "s", "alts")})
    out = {}
    for (away, home, start), ps in games.items():
        out[f"{away}_{home}_{start}"] = {"start": {"integerValue": str(start)}, "asof": {"integerValue": str(int(asof or 0))},
                                         "credit": {"stringValue": "Prices via SmartStake"}, "json": {"stringValue": json.dumps(ps, separators=(",", ":"))}}
    return out


def rest(token, method, path, body=None):
    url = f"https://firestore.googleapis.com/v1/projects/{PROJECT}/databases/(default)/documents/{path}"
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None, method=method,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"Firestore {method} {path}: HTTP {e.code} {e.read().decode()[:300]}")


PROJECT = "vault-fantasy"


def main(argv):
    dry = "--dry" in argv
    off = OFF.exists() or os.environ.get("SMARTSTAKE_PUBLISH") == "0"
    asof, props = (None, []) if off else A.build(AHEAD_H)
    docs = docs_for(props, asof)
    n = sum(len(p["alts"]) for p in props)
    print(f"{'OFF: deleting every document' if off else f'{len(props)} props, {n} book lines'} in {len(docs)} game documents, {sum(len(d['json']['stringValue']) for d in docs.values()) // 1000} KB")
    if dry:
        return
    if not SA.exists():
        sys.exit("No service account key at ~/.config/smartstake/firebase-sa.json. Nothing was published.")
    digest = hashlib.sha1(json.dumps(docs, sort_keys=True).encode()).hexdigest()
    token = access_token(json.loads(SA.read_text()))
    if not (LAST.exists() and LAST.read_text().strip() == digest):
        for did, fields in docs.items():
            rest(token, "PATCH", f"{COLL}/{did}", {"fields": fields})
        have = rest(token, "GET", f"{COLL}?pageSize=300").get("documents", [])
        gone = [d["name"].rsplit("/", 1)[-1] for d in have if d["name"].rsplit("/", 1)[-1] not in docs and (off or not d["name"].rsplit("/", 1)[-1].startswith("_"))]
        for did in gone:
            rest(token, "DELETE", f"{COLL}/{did}")
        LAST.parent.mkdir(parents=True, exist_ok=True)
        LAST.write_text(digest)
        print(f"wrote {len(docs)} documents, removed {len(gone)}")
    else:
        print("alts unchanged, not written")
    if off:
        return
    try:                                                           # the Combo Check record: track the calls, settle, write the summary
        import combo_calls
        rec = combo_calls.run()
        if rec:
            rest(token, "PATCH", f"{COLL}/_record", {"fields": {"asof": {"integerValue": str(rec["asof"])}, "json": {"stringValue": json.dumps(rec, separators=(",", ":"))}}})
    except Exception as e:                                         # never let the record break the prices
        print("combo record failed:", repr(e))
    try:                                                           # Bankroll Builder: new picks, followed prices, settlement; then the backtest record if one exists
        import bankroll_builder
        rec = bankroll_builder.run()
        if rec:
            rest(token, "PATCH", f"{COLL}/_bankroll", {"fields": {"asof": {"integerValue": str(rec["asof"])}, "json": {"stringValue": json.dumps(rec, separators=(",", ":"))}}})
        bt = bankroll_builder.BT_RECORD
        if bt.exists() and (not BT_LAST.exists() or BT_LAST.read_text().strip() != str(int(bt.stat().st_mtime))):
            body = bt.read_text()
            rest(token, "PATCH", f"{COLL}/_bankroll_bt", {"fields": {"asof": {"integerValue": str(json.loads(body).get("asof", 0))}, "json": {"stringValue": body}}})
            BT_LAST.write_text(str(int(bt.stat().st_mtime)))
    except Exception as e:
        print("bankroll record failed:", repr(e))


if __name__ == "__main__":
    main(sys.argv[1:])
