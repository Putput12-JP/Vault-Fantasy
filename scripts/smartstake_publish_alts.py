"""Publish the current NBA alternate-line prices from the SmartStake tape, ENCRYPTED, for the Vault NBA page's Combo Check.

  python3 scripts/smartstake_publish_alts.py            # build, encrypt and push once
  python3 scripts/smartstake_publish_alts.py --dry      # build and report only (nothing written or pushed)

SmartStake's API terms allow storing the data for internal research and require written permission to show it to users of our own
product. The page is public, so the prices are never published in the clear: they are encrypted with a password only the owner
knows (AES-256-CBC, key from PBKDF2-SHA256 at 250,000 rounds, an OpenSSL "Salted__" blob), and the page asks for that password once in
the browser and decrypts there. What sits on GitHub is ciphertext. The page credits SmartStake once unlocked.

PASSWORD: put it in the file ~/.config/smartstake/publish.key (one line, readable only by you) or in the SMARTSTAKE_ALTS_PASSWORD
environment variable. With no password the script refuses to publish. Never put it in the repo.

What is encrypted and pushed: one file, alts.enc, on the orphan branch `nba-alts` (one commit, force-pushed, no history): per player-prop
the alternate-line prices each book is posting, pregame games starting within the next 36 hours only.

KILL SWITCH: create ~/.config/smartstake/publish.off (or set SMARTSTAKE_PUBLISH=0): the next run pushes an empty list. To remove it:
`git push origin --delete nba-alts`.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smartstake_alts as A

CHECKOUT = os.environ.get("SMARTSTAKE_CHECKOUT", "/Users/jacobputman/Desktop/Draft Tool")
BRANCH = "nba-alts"
AHEAD_H = 36
ITER = 250000
CONF = Path.home() / ".config" / "smartstake"
OFF, KEY, LAST = CONF / "publish.off", CONF / "publish.key", CONF / "publish.last"


def git(*args, input=None):
    return subprocess.run(["git", "-C", CHECKOUT, *args], input=input, capture_output=True, text=True, check=True).stdout.strip()


def password():
    if os.environ.get("SMARTSTAKE_ALTS_PASSWORD"):
        return os.environ["SMARTSTAKE_ALTS_PASSWORD"]
    return KEY.read_text().strip() if KEY.exists() else None


def encrypt(body, pw):
    """OpenSSL AES-256-CBC with PBKDF2-SHA256 (what the page's WebCrypto decrypts): base64 of 'Salted__' + salt + ciphertext."""
    env = dict(os.environ, SS_ALTS_PW=pw)
    out = subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-md", "sha256", "-iter", str(ITER), "-salt", "-a", "-A", "-pass", "env:SS_ALTS_PW"],
                         input=body.encode(), capture_output=True, env=env, check=True).stdout
    return out.decode()


def main(argv):
    dry = "--dry" in argv
    off = OFF.exists() or os.environ.get("SMARTSTAKE_PUBLISH") == "0"
    asof, props = (None, []) if off else A.build(AHEAD_H)
    n = sum(len(p["alts"]) for p in props)
    print(f"{'OFF: publishing an empty list' if off else f'{len(props)} props, {n} book lines'}")
    if dry:
        return
    pw = password()
    if not pw:
        sys.exit("No password: put one in ~/.config/smartstake/publish.key or SMARTSTAKE_ALTS_PASSWORD. Nothing was published.")
    body = json.dumps({"source": "SmartStake", "asof": asof, "props": props}, separators=(",", ":"))
    digest = hashlib.sha1((body + str(off)).encode()).hexdigest()
    if LAST.exists() and LAST.read_text().strip() == digest:
        print("unchanged, not pushed")
        return
    blob = git("hash-object", "-w", "--stdin", input=encrypt(body, pw))
    tree = git("mktree", input=f"100644 blob {blob}\talts.enc\n")
    commit = git("-c", "user.name=Vault alts", "-c", "user.email=noreply@vaultfantasy.com", "commit-tree", tree, "-m", "encrypted alternate-line prices")
    git("push", "--force", "-q", "origin", f"{commit}:refs/heads/{BRANCH}")
    LAST.parent.mkdir(parents=True, exist_ok=True)
    LAST.write_text(digest)
    print("pushed (encrypted)", commit[:8])


if __name__ == "__main__":
    main(sys.argv[1:])
