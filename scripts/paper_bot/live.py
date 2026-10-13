"""Disabled Kalshi trading interface.

THIS FILE DOES NOT PLACE ORDERS.

Paper trading is the only path this repository runs. `place_order` raises
every time, before any network call. There is no order HTTP request in this
file to turn on. A later change that wants live trading has to replace
`LiveBroker.place_order` with a real implementation and review it on its own.
Setting `paper_only`, `kill_switch`, `KALSHI_API_KEY`, or `KALSHI_PRIVATE_KEY`
does not enable anything here.

What IS here, so that later change has less to invent:

  * The request signature Kalshi's trade API expects: RSA-PSS with SHA-256
    over `{timestamp_ms}{METHOD}{path}`. `path` is the path beginning with
    `/trade-api/v2`, without the query string.
  * Headers `KALSHI-ACCESS-KEY`, `KALSHI-ACCESS-TIMESTAMP`, `KALSHI-ACCESS-SIGNATURE`.
  * The key id comes from the env var `KALSHI_API_KEY`. The PEM private key
    comes from `KALSHI_PRIVATE_KEY` (the PEM text) or `KALSHI_PRIVATE_KEY_PATH`
    (a file). Neither is read unless something calls `KalshiSigner.from_env`.

The paper bot never constructs a signer and never calls `place_order`.
"""
import base64
import os

# Hard-coded off. Not read from config or the environment.
# Flipping this constant still does not place an order: there is no order call under it.
LIVE_ORDERS_IMPLEMENTED = False


class LiveTradingDisabled(RuntimeError):
    """Raised for every attempt to send an order. That is the intended result."""


class KalshiSigner:
    """Builds the signed headers. Does not send them."""

    def __init__(self, key_id, private_key_pem):
        if not key_id or not private_key_pem:
            raise LiveTradingDisabled('Kalshi key id or private key is missing')
        self.key_id = key_id
        self._pem = private_key_pem if isinstance(private_key_pem, bytes) else str(private_key_pem).encode('utf-8')

    @classmethod
    def from_env(cls, env=None):
        env = env if env is not None else os.environ
        pem = env.get('KALSHI_PRIVATE_KEY') or ''
        path = env.get('KALSHI_PRIVATE_KEY_PATH') or ''
        if not pem and path:
            with open(path, 'rb') as f:
                pem = f.read()
        return cls(env.get('KALSHI_API_KEY') or '', pem)

    def headers(self, method, path, timestamp_ms):
        """Signed headers for one request. `path` includes `/trade-api/v2` and no query."""
        sig = self.sign(method, path, timestamp_ms)
        return {
            'KALSHI-ACCESS-KEY': self.key_id,
            'KALSHI-ACCESS-TIMESTAMP': str(int(timestamp_ms)),
            'KALSHI-ACCESS-SIGNATURE': sig,
        }

    def sign(self, method, path, timestamp_ms):
        message = f'{int(timestamp_ms)}{method.upper()}{path.split("?", 1)[0]}'.encode('utf-8')
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
        except ImportError as e:
            raise LiveTradingDisabled('the cryptography package is required to sign a Kalshi request') from e
        key = serialization.load_pem_private_key(self._pem, password=None)
        signature = key.sign(
            message,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode('ascii')


class LiveBroker:
    """The live broker. `place_order` cannot succeed in this repository."""

    def __init__(self, *args, **kwargs):
        # Accept and ignore whatever a future caller might pass. Nothing is stored
        # that could be posted, and nothing is connected.
        self.args = args
        self.enabled = False

    def place_order(self, *args, **kwargs):
        if LIVE_ORDERS_IMPLEMENTED:
            # Still no order call. Reaching this line means someone flipped the
            # constant without writing the order. Refuse rather than guess.
            raise LiveTradingDisabled(
                'LIVE_ORDERS_IMPLEMENTED was flipped but order placement was never written. Refusing.'
            )
        raise LiveTradingDisabled(
            'Live order placement is not implemented. This paper bot never sends orders. '
            'A config flag, KALSHI_API_KEY, or KALSHI_PRIVATE_KEY does not enable it. '
            'A later change has to replace LiveBroker.place_order.'
        )
