"""One-off: open a subaccount (trading key) and issue a read-only key. Needs the management key in env."""
import json, os, sys
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
sys.path.insert(0, os.path.dirname(__file__))
import novig_client as nc

D = os.path.expanduser("~/.novig")

def newkey(name):
    k = ed25519.Ed25519PrivateKey.generate()
    open(f"{D}/{name}.pem", "wb").write(k.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    os.chmod(f"{D}/{name}.pem", 0o600)
    return k.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()

body = json.dumps({"label": "vault-desk", "publicKey": newkey("desk"), "algorithm": "Ed25519"}).encode()
r = nc.request("POST", "/v3/account/subaccounts", body=body)
print("open subaccount:", r.status_code, r.text[:400])
r.raise_for_status()
sub = r.json()["keyId"]
body = json.dumps({"name": "vault-reader", "publicKey": newkey("reader"), "algorithm": "Ed25519",
                   "scope": "trading::read"}).encode()
r = nc.request("POST", f"/v3/account/subaccounts/{sub}/keys", body=body)
print("read key:", r.status_code, r.text[:400])
