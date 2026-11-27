"""
In-memory stand-in for ``web3.Web3`` that behaves like a JSON-RPC node, so the live
service can be tested without a network, funds or the web3 package.

Node rules it enforces (the ones the service must cope with):
  * hashes must be 0x-prefixed strings or bytes ("hex string without 0x prefix")
  * a nonce can be used once: a different tx with a used nonce is rejected
    ("Invalid transaction nonce" once mined - eth-tester's wording, deliberately not
    geth's "nonce too low" - or "replacement transaction underpriced" while pending)
  * get_transaction_count: "pending" counts the pool, "latest" only mined txs
  * get_transaction also returns pending txs (blockNumber None), like geth
  * re-sending identical bytes is accepted (or "already known", if configured)
  * receipts only exist once mined; waiting on a pending tx raises TimeExhausted

It is thread-safe so it can back concurrency tests.
"""
import hashlib
import json
import threading

GWEI = 10**9
WALLET = "0x1111111111111111111111111111111111111111"
OTHER = "0x2222222222222222222222222222222222222222"


class HexBytes(bytes):
    """Mirrors hexbytes>=1.0 (web3 v7/v8): .hex() has no 0x prefix."""


class LegacyHexBytes(bytes):
    """Mirrors hexbytes<1.0 (web3 v6): .hex() is 0x-prefixed."""

    def hex(self):  # noqa: D401
        return "0x" + super().hex()


class AttrDict(dict):
    __getattr__ = dict.__getitem__


# Same class names as web3.exceptions; the service matches on the name.
class TransactionNotFound(Exception):
    pass


class TimeExhausted(Exception):
    pass


class RPCError(ValueError):
    pass


def key(value):
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    if not (isinstance(value, str) and value.startswith("0x")):
        raise ValueError("invalid argument 0: hex string without 0x prefix")
    return bytes.fromhex(value[2:])


class FakeEth:
    def __init__(self, hexbytes_cls=HexBytes, receipt_status=1, sender=None, auto_mine=True,
                 stale_pending_nonce=False, base_fee=10 * GWEI, suggested_tip=2 * GWEI,
                 gas_estimate=22_024, legacy=False, already_known_error=False, gas_price=50 * GWEI):
        self._lock = threading.RLock()
        self.hexbytes_cls = hexbytes_cls
        self.receipt_status = receipt_status
        self.sender = sender
        self.auto_mine = auto_mine
        self.stale_pending_nonce = stale_pending_nonce
        self.base_fee = base_fee
        self.suggested_tip = suggested_tip
        self.gas_estimate = gas_estimate
        self.legacy = legacy
        self.already_known_error = already_known_error
        self.gas_price = gas_price
        self.chain_id = 80002
        self.account = self

        self.pool = {}          # hash -> tx (pending)
        self.txs = {}           # hash -> AttrDict (mined)
        self.receipts = {}      # hash -> AttrDict
        self.nonce_owner = {}   # nonce -> hash
        self.signed = []        # every tx dict passed to sign_transaction
        self.accepted = []      # hashes accepted into the pool (first time only)
        self.send_calls = 0
        self.estimate_calls = []
        self.block = 5000
        self.rpc_error = None
        self.send_error = None  # exception raised by the next send_raw_transaction

    # --- reads used when building a transaction ----------------------------------
    def get_transaction_count(self, address, block_identifier=None):
        with self._lock:
            if block_identifier == "latest":
                return max((tx["nonce"] for tx in self.txs.values()), default=-1) + 1
            if self.stale_pending_nonce:
                return 0  # a lagging / load-balanced RPC node
            return max(self.nonce_owner, default=-1) + 1

    def estimate_gas(self, tx):
        self.estimate_calls.append(tx)
        return self.gas_estimate

    def get_block(self, identifier):
        block = AttrDict(number=self.block)
        if not self.legacy:
            block["baseFeePerGas"] = self.base_fee
        return block

    @property
    def max_priority_fee(self):
        return self.suggested_tip

    # --- signing / sending ----------------------------------------------------------
    def sign_transaction(self, tx, private_key):
        with self._lock:
            self.signed.append(dict(tx))
        payload = {k: (v.hex() if isinstance(v, bytes) else v) for k, v in tx.items()}
        raw = json.dumps(payload, sort_keys=True).encode()
        return AttrDict(raw_transaction=self.hexbytes_cls(raw),
                        hash=self.hexbytes_cls(hashlib.sha256(raw).digest()))

    def send_raw_transaction(self, raw):
        with self._lock:
            self.send_calls += 1
            if self.send_error is not None:
                err, self.send_error = self.send_error, None
                raise err
            raw = key(raw) if isinstance(raw, str) else bytes(raw)
            h = hashlib.sha256(raw).digest()
            if h in self.pool or h in self.txs:
                if self.already_known_error:
                    raise RPCError({"code": -32000, "message": "already known"})
                return self.hexbytes_cls(h)
            tx = json.loads(raw)
            owner = self.nonce_owner.get(tx["nonce"])
            if owner is not None and owner != h:
                if owner in self.txs:
                    raise RPCError("Invalid transaction nonce: Expected higher")
                raise RPCError({"code": -32000, "message": "replacement transaction underpriced"})
            self.nonce_owner[tx["nonce"]] = h
            self.pool[h] = tx
            self.accepted.append(h)
            if self.auto_mine:
                self.mine()
            return self.hexbytes_cls(h)

    def mine(self):
        with self._lock:
            for h, tx in sorted(self.pool.items(), key=lambda kv: kv[1]["nonce"]):
                self.block += 1
                self.txs[h] = AttrDict({
                    "hash": self.hexbytes_cls(h),
                    "input": self.hexbytes_cls(bytes.fromhex(tx["data"])),
                    "blockNumber": self.block,
                    "from": self.sender or tx["from"],
                    "to": tx["to"],
                    "nonce": tx["nonce"],
                })
                self.receipts[h] = AttrDict(transactionHash=self.hexbytes_cls(h),
                                            blockNumber=self.block, status=self.receipt_status)
            self.pool.clear()

    def take_nonce_externally(self, nonce):
        """Simulate another client (or a manual transfer) mining a tx with ``nonce``."""
        with self._lock:
            h = hashlib.sha256(f"external-{nonce}".encode()).digest()
            self.nonce_owner[nonce] = h
            self.block += 1
            self.txs[h] = AttrDict({"hash": h, "input": b"", "blockNumber": self.block,
                                    "from": WALLET, "to": OTHER, "nonce": nonce})
            self.receipts[h] = AttrDict(transactionHash=h, blockNumber=self.block, status=1)

    # --- reading ------------------------------------------------------------------------
    def wait_for_transaction_receipt(self, tx_hash, timeout=120, poll_latency=0.1):
        with self._lock:
            k = key(tx_hash)
            if k in self.receipts:
                return self.receipts[k]
        raise TimeExhausted(f"{tx_hash} not in chain after {timeout}s")

    def get_transaction(self, tx_hash):
        with self._lock:
            if self.rpc_error:
                raise self.rpc_error
            k = key(tx_hash)
            if k in self.pool:
                tx = self.pool[k]
                return AttrDict({"hash": self.hexbytes_cls(k), "input": self.hexbytes_cls(bytes.fromhex(tx["data"])),
                                 "blockNumber": None, "from": tx["from"], "to": tx["to"], "nonce": tx["nonce"]})
            if k not in self.txs:
                raise TransactionNotFound(tx_hash)
            return self.txs[k]

    def get_transaction_receipt(self, tx_hash):
        with self._lock:
            if self.rpc_error:
                raise self.rpc_error
            k = key(tx_hash)
            if k not in self.receipts:
                raise TransactionNotFound(tx_hash)
            return self.receipts[k]


class FakeW3:
    def __init__(self, **kwargs):
        self.eth = FakeEth(**kwargs)

    def is_connected(self):
        return True
