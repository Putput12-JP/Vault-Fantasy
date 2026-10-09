"""Minimal NOVIG-V3 signed client. Key path/ID/host come from env; no secrets in the repo.

  NOVIG_KEY_ID    key UUID (not secret)
  NOVIG_KEY_PATH  path to the private key PEM (Ed25519 or P-256)
  NOVIG_HOST      https://api.paper.novig.com (default) or https://api.novig.com
"""
import base64, hashlib, os, sys, time
from urllib.parse import quote, unquote_to_bytes

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519

HOST = os.environ.get("NOVIG_HOST", "https://api.paper.novig.com")


def _canon_query(raw):
    if not raw:
        return ""
    pairs = []
    for part in raw.split("&"):
        k, _, v = part.partition("=")
        enc = lambda s: quote(unquote_to_bytes(s.replace("+", "%2B")), safe="-._~")
        pairs.append((enc(k), enc(v)))
    return "&".join(f"{k}={v}" for k, v in sorted(pairs))


def _load_key(path):
    with open(path, "rb") as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def sign(key, method, path, query="", body=b"", ts=None):
    ts = str(ts or int(time.time() * 1000))
    s = "\n".join(["NOVIG-V3", ts, method.upper(), path, _canon_query(query),
                   hashlib.sha256(body).hexdigest()])
    if isinstance(key, ed25519.Ed25519PrivateKey):
        sig = key.sign(s.encode())
    else:
        sig = key.sign(s.encode(), ec.ECDSA(hashes.SHA256()))
    return ts, base64.b64encode(sig).decode()


def request(method, path, query="", body=b""):
    key = _load_key(os.environ["NOVIG_KEY_PATH"])
    ts, sig = sign(key, method, path, query, body)
    headers = {"Novig-Key-Id": os.environ["NOVIG_KEY_ID"], "Novig-Timestamp": ts,
               "Novig-Signature": sig, "Content-Type": "application/json"}
    url = HOST + path + (f"?{query}" if query else "")
    return requests.request(method, url, headers=headers, data=body, timeout=15)


if __name__ == "__main__":
    r = request("POST", "/v3/echo", body=b'{"hello":"vault"}')
    print(r.status_code, r.text[:300])
