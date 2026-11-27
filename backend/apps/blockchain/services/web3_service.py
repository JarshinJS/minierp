import logging
import math
import os
import secrets
import time

from django.conf import settings
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F

logger = logging.getLogger(__name__)


class Web3ServiceError(Exception):
    """Raised when a Web3 operation fails (misconfiguration, RPC/network error, reverted tx)."""
    pass


# ---------------------------------------------------------------------------
# Hex helpers
# ---------------------------------------------------------------------------
# web3 v7 depends on hexbytes>=1.0, whose HexBytes.hex() returns hex WITHOUT the
# "0x" prefix (older versions included it). JSON-RPC nodes only accept 0x-prefixed
# hashes, so every value is normalised here instead of relying on .hex().

def _strip_0x(value):
    return value[2:] if value[:2] in ("0x", "0X") else value


def normalize_tx_hash(value):
    """Return a transaction hash as a lowercase, 0x-prefixed hex string."""
    if isinstance(value, (bytes, bytearray)):
        return "0x" + bytes(value).hex()
    return "0x" + _strip_0x(str(value).strip()).lower()


def decode_input_data(value):
    """Return transaction input data as raw bytes (accepts bytes/HexBytes or hex str)."""
    if value is None:
        return b""
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return bytes.fromhex(_strip_0x(value))


def _get(obj, key, default=None):
    """Read a field from a web3 AttributeDict / dict."""
    try:
        return obj[key]
    except (KeyError, TypeError, IndexError):
        pass
    try:
        return getattr(obj, key)
    except (AttributeError, KeyError):
        return default


def _error_text(exc):
    return str(exc).lower()


def _is_error(exc, *names):
    return type(exc).__name__ in names


def _checksum(address):
    """Checksummed address when web3 is available (web3 rejects lower-case addresses)."""
    try:
        from web3 import Web3
    except ImportError:
        return address
    return Web3.to_checksum_address(address)


GWEI = 10**9
# Contention on the wallet row: Postgres blocks on the row lock, SQLite (dev) raises
# "database is locked"; retry those a few times before giving up.
_LOCK_RETRIES = 20


def _not_found(expected_hash):
    return {
        "verified": False,
        "found": False,
        "reason": "Transaction not found",
        "expected_hash": expected_hash,
        "stored_hash": None,
    }


# ---------------------------------------------------------------------------
# Mock implementation (database-backed)
# ---------------------------------------------------------------------------

class MockWeb3Service:
    """
    Simulates blockchain operations for development and demos.

    Transactions are stored in the MockBlockchainTransaction table so they are shared
    by all processes (web workers, Celery workers) and survive restarts. This gives
    NO tamper resistance: anyone with database access can edit the simulated ledger.
    """

    network_name = "mock-network"
    chain_id = 0

    def is_connected(self):
        return True

    def get_network_info(self):
        return {
            "chain_id": self.chain_id,
            "network_name": self.network_name,
            "is_mock": True,
        }

    def submit_data_hash(self, data_hash):
        """Simulate submitting a hash to the blockchain."""
        from apps.blockchain.models import MockBlockchainTransaction

        txn, _ = MockBlockchainTransaction.objects.get_or_create(
            input_data=data_hash,
            defaults={"txn_hash": "0x" + secrets.token_hex(32)},
        )
        logger.info("Mock blockchain: stored hash %s in tx %s", data_hash, txn.txn_hash)
        return txn.txn_hash

    def get_transaction(self, txn_hash):
        """Retrieve a mock transaction, or None if it does not exist."""
        from apps.blockchain.models import MockBlockchainTransaction

        txn = MockBlockchainTransaction.objects.filter(txn_hash=normalize_tx_hash(txn_hash)).first()
        if not txn:
            return None
        return {
            "hash": txn.txn_hash,
            "input_data": txn.input_data,
            "block_number": txn.block_number,
            "status": txn.status,
        }

    def verify_data_hash(self, txn_hash, expected_hash):
        """Verify a hash against the stored mock transaction."""
        txn = self.get_transaction(txn_hash)
        if not txn:
            return _not_found(expected_hash)
        stored_hash = txn["input_data"]
        is_match = stored_hash == expected_hash
        return {
            "verified": is_match,
            "found": True,
            "stored_hash": stored_hash,
            "expected_hash": expected_hash,
            "reason": "Match" if is_match else "Hash mismatch",
        }


# ---------------------------------------------------------------------------
# Live implementation
# ---------------------------------------------------------------------------

class LiveWeb3Service:
    """
    Real Web3 service that connects to a Polygon (or compatible) network.
    Requires WEB3_PROVIDER_URL, BLOCKCHAIN_WALLET_ADDRESS, and the
    BLOCKCHAIN_WALLET_PRIVATE_KEY environment variable.

    ``w3`` may be passed in (e.g. a test double); otherwise one is built from settings.
    """

    def __init__(self, w3=None):
        if w3 is None:
            w3 = self._connect()
        self.w3 = w3
        self.wallet_address = getattr(settings, "BLOCKCHAIN_WALLET_ADDRESS", "")
        self.network_name = getattr(settings, "BLOCKCHAIN_NETWORK_NAME", "polygon-amoy")
        self.chain_id = self.w3.eth.chain_id
        logger.info("Web3 connected to %s (chain %d)", self.network_name, self.chain_id)

    @staticmethod
    def _connect():
        try:
            from web3 import Web3
        except ImportError:
            raise Web3ServiceError("web3 package is not installed. Run: pip install web3")

        provider_url = getattr(settings, "WEB3_PROVIDER_URL", "")
        if not provider_url:
            raise Web3ServiceError("WEB3_PROVIDER_URL is not configured.")

        w3 = Web3(Web3.HTTPProvider(provider_url, request_kwargs={"timeout": 30}))
        # Polygon is a PoA chain: blocks carry >32 bytes of extraData, which web3
        # rejects unless this middleware is installed (needed for get_block()).
        from web3.middleware import ExtraDataToPOAMiddleware
        w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        if not w3.is_connected():
            # Do not echo the URL: provider URLs commonly embed an API key.
            raise Web3ServiceError("Cannot connect to the configured Web3 provider.")
        return w3

    def is_connected(self):
        try:
            return bool(self.w3.is_connected())
        except Exception:
            return False

    def get_network_info(self):
        return {
            "chain_id": self.chain_id,
            "network_name": self.network_name,
            "is_mock": False,
        }

    # --- submission ---------------------------------------------------------------
    #
    # 1. allocate   (wallet row locked)  nonce = max(node pending count, our next_nonce),
    #               build + sign, persist BlockchainSubmission(SIGNED). Lock released.
    # 2. broadcast  send the stored raw bytes. Re-sending is harmless: same tx hash.
    # 3. confirm    wait for the receipt. On timeout the submission stays BROADCAST and
    #               Web3ServiceError is raised; the Celery retry resumes at step 2
    #               with the same transaction, so nothing is ever double-submitted.

    def submit_data_hash(self, data_hash):
        """Anchor ``data_hash`` on-chain (idempotent per wallet + hash). Returns the 0x tx hash."""
        from apps.blockchain.models import BlockchainSubmission

        private_key = os.getenv("BLOCKCHAIN_WALLET_PRIVATE_KEY", "")
        if not private_key:
            raise Web3ServiceError("BLOCKCHAIN_WALLET_PRIVATE_KEY is not set.")
        if not self.wallet_address:
            raise Web3ServiceError("BLOCKCHAIN_WALLET_ADDRESS is not set.")

        for _ in range(3):  # a fresh allocation is needed only if our nonce was taken
            sub = self._allocate_submission(data_hash, private_key)
            if sub.status == BlockchainSubmission.Status.CONFIRMED:
                return sub.txn_hash
            self._rebroadcast_earlier(sub)
            if self._send_raw(sub):
                return self._confirm(sub)
        raise Web3ServiceError("Could not obtain a usable nonce; will retry.")

    def _wallet(self):
        from apps.blockchain.models import BlockchainWallet

        wallet, _ = BlockchainWallet.objects.get_or_create(
            address=self.wallet_address.lower(), chain_id=self.chain_id,
        )
        return wallet

    def _allocate_submission(self, data_hash, private_key):
        from apps.blockchain.models import BlockchainSubmission, BlockchainWallet

        wallet = self._wallet()
        active = BlockchainSubmission.objects.filter(
            wallet=wallet, data_hash=data_hash, status__in=BlockchainSubmission.ACTIVE,
        )
        for attempt in range(_LOCK_RETRIES):
            try:
                with transaction.atomic():
                    # Write first: takes the row lock on Postgres and the write lock on
                    # SQLite before anything is read, so allocations are serialised.
                    BlockchainWallet.objects.filter(pk=wallet.pk).update(next_nonce=F("next_nonce"))
                    locked = BlockchainWallet.objects.select_for_update().get(pk=wallet.pk)

                    existing = active.first()
                    if existing:
                        return existing

                    try:
                        chain_nonce = self.w3.eth.get_transaction_count(_checksum(self.wallet_address), "pending")
                    except Exception as e:
                        raise Web3ServiceError(f"Nonce lookup failed: {type(e).__name__}") from e
                    nonce = max(chain_nonce, locked.next_nonce)
                    tx = self._build_transaction(nonce, data_hash)
                    try:
                        signed = self.w3.eth.account.sign_transaction(tx, private_key)
                    except Exception as e:
                        # Type name only: signing errors must never echo key material.
                        raise Web3ServiceError(f"Signing failed: {type(e).__name__}") from None
                    sub = BlockchainSubmission.objects.create(
                        wallet=locked, data_hash=data_hash, nonce=nonce,
                        txn_hash=normalize_tx_hash(signed.hash),
                        raw_transaction="0x" + bytes(signed.raw_transaction).hex(),
                    )
                    locked.next_nonce = nonce + 1
                    locked.save(update_fields=["next_nonce", "updated_at"])
                    return sub
            except IntegrityError:
                # Another worker created the submission for this hash first.
                existing = active.first()
                if existing:
                    return existing
                raise
            except OperationalError as e:
                if "locked" not in _error_text(e) or attempt == _LOCK_RETRIES - 1:
                    raise
                time.sleep(min(0.05 * (attempt + 1), 0.5))
        raise Web3ServiceError("Wallet nonce lock unavailable.")  # pragma: no cover

    def _build_transaction(self, nonce, data_hash):
        address = _checksum(self.wallet_address)
        data = data_hash.encode("utf-8")
        try:
            estimate = self.w3.eth.estimate_gas({"from": address, "to": address, "value": 0, "data": data})
        except Exception as e:
            raise Web3ServiceError(f"Gas estimation failed: {type(e).__name__}") from e

        gas = math.ceil(estimate * settings.BLOCKCHAIN_GAS_LIMIT_MULTIPLIER)
        if gas > settings.BLOCKCHAIN_MAX_GAS:
            raise Web3ServiceError(
                f"Estimated gas {gas} exceeds BLOCKCHAIN_MAX_GAS={settings.BLOCKCHAIN_MAX_GAS}."
            )

        tx = {
            "nonce": nonce, "from": address, "to": address, "value": 0,
            "gas": gas, "data": data, "chainId": self.chain_id,
        }
        tx.update(self._fee_fields())
        return tx

    def _fee_fields(self):
        max_fee_cap = int(settings.BLOCKCHAIN_MAX_FEE_PER_GAS_GWEI * GWEI)
        try:
            base_fee = _get(self.w3.eth.get_block("latest"), "baseFeePerGas")
            if base_fee is None:  # pre-London chain: legacy pricing
                gas_price = int(self.w3.eth.gas_price)
                if gas_price > max_fee_cap:
                    raise Web3ServiceError(
                        f"Gas price {gas_price / GWEI:.1f} gwei exceeds the "
                        f"{settings.BLOCKCHAIN_MAX_FEE_PER_GAS_GWEI} gwei cap; will retry."
                    )
                return {"gasPrice": gas_price}
            suggested_tip = int(self.w3.eth.max_priority_fee)
        except Web3ServiceError:
            raise
        except Exception as e:
            raise Web3ServiceError(f"Fee lookup failed: {type(e).__name__}") from e

        tip = max(suggested_tip, int(settings.BLOCKCHAIN_MIN_PRIORITY_FEE_GWEI * GWEI))
        max_fee = 2 * int(base_fee) + tip  # headroom for base-fee rises over ~6 blocks
        if max_fee > max_fee_cap:
            raise Web3ServiceError(
                f"Max fee {max_fee / GWEI:.1f} gwei exceeds the "
                f"{settings.BLOCKCHAIN_MAX_FEE_PER_GAS_GWEI} gwei cap; will retry."
            )
        return {"type": 2, "maxFeePerGas": max_fee, "maxPriorityFeePerGas": tip}

    def _send_raw(self, sub):
        """Broadcast a stored submission. True if the node has (or had) it; False if its nonce was taken."""
        from apps.blockchain.models import BlockchainSubmission

        S = BlockchainSubmission.Status
        BlockchainSubmission.objects.filter(pk=sub.pk).update(broadcast_attempts=sub.broadcast_attempts + 1)
        sub.broadcast_attempts += 1
        try:
            self.w3.eth.send_raw_transaction(sub.raw_transaction)
        except Exception as e:
            # Node clients word these errors differently ("already known", "nonce too
            # low", "Invalid transaction nonce", ...), so decide from chain state, not
            # from the message: is OUR transaction known? Otherwise, was our nonce used?
            text = _error_text(e)
            if "already known" in text or "known transaction" in text or self._known_to_node(sub.txn_hash):
                pass  # the node already has (or has mined) exactly this transaction
            elif self._nonce_consumed(sub.nonce):
                BlockchainSubmission.objects.filter(pk=sub.pk).update(
                    status=S.REPLACED, last_error="nonce consumed by another transaction")
                sub.status = S.REPLACED
                logger.warning("Nonce %s for tx %s was consumed elsewhere; re-allocating.",
                               sub.nonce, sub.txn_hash)
                return False
            else:
                BlockchainSubmission.objects.filter(pk=sub.pk).update(last_error=type(e).__name__)
                raise Web3ServiceError(f"Broadcast failed: {type(e).__name__}") from e

        if sub.status == S.SIGNED:
            BlockchainSubmission.objects.filter(pk=sub.pk, status=S.SIGNED).update(status=S.BROADCAST)
            sub.status = S.BROADCAST
        return True

    def _rebroadcast_earlier(self, sub):
        """
        Re-send our own earlier transactions that the node may have lost (e.g. a worker
        died between signing and broadcasting). Otherwise that nonce gap would leave
        every later transaction stuck in the node's queue. Best effort.
        """
        from apps.blockchain.models import BlockchainSubmission

        stale = BlockchainSubmission.objects.filter(
            wallet_id=sub.wallet_id, nonce__lt=sub.nonce,
            status__in=[BlockchainSubmission.Status.SIGNED, BlockchainSubmission.Status.BROADCAST],
        ).order_by("nonce")[:20]
        for earlier in stale:
            try:
                self._send_raw(earlier)
            except Web3ServiceError as e:
                logger.warning("Re-broadcast of tx %s failed: %s", earlier.txn_hash, e)

    def _known_to_node(self, txn_hash):
        """True if the node has this transaction, pending or mined."""
        try:
            self.w3.eth.get_transaction(txn_hash)
            return True
        except Exception as e:
            if _is_error(e, "TransactionNotFound"):
                return False
            raise Web3ServiceError(f"Transaction lookup failed: {type(e).__name__}") from e

    def _nonce_consumed(self, nonce):
        """True if a mined transaction from our wallet already used ``nonce``."""
        try:
            mined = self.w3.eth.get_transaction_count(_checksum(self.wallet_address), "latest")
        except Exception as e:
            raise Web3ServiceError(f"Nonce lookup failed: {type(e).__name__}") from e
        return mined > nonce

    def _confirm(self, sub):
        from apps.blockchain.models import BlockchainSubmission

        S = BlockchainSubmission.Status
        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(
                sub.txn_hash, timeout=settings.BLOCKCHAIN_RECEIPT_TIMEOUT, poll_latency=2,
            )
        except Exception as e:
            if _is_error(e, "TimeExhausted"):
                raise Web3ServiceError(
                    f"Transaction {sub.txn_hash} not mined within "
                    f"{settings.BLOCKCHAIN_RECEIPT_TIMEOUT}s; it stays pending and will be re-checked."
                ) from e
            raise Web3ServiceError(f"Receipt polling failed: {type(e).__name__}") from e

        block = _get(receipt, "blockNumber")
        if _get(receipt, "status") != 1:
            BlockchainSubmission.objects.filter(pk=sub.pk).update(
                status=S.FAILED, block_number=block, last_error="reverted")
            raise Web3ServiceError(f"Transaction {sub.txn_hash} reverted on-chain.")

        BlockchainSubmission.objects.filter(pk=sub.pk).update(status=S.CONFIRMED, block_number=block)
        logger.info("Blockchain tx confirmed: %s (nonce %s, block %s)", sub.txn_hash, sub.nonce, block)
        return sub.txn_hash

    def get_transaction(self, txn_hash):
        """
        Retrieve transaction details from the blockchain.
        Returns None if the transaction does not exist; raises Web3ServiceError on RPC errors.
        """
        txn_hash = normalize_tx_hash(txn_hash)
        try:
            txn = self.w3.eth.get_transaction(txn_hash)
            receipt = self.w3.eth.get_transaction_receipt(txn_hash)
        except Exception as e:
            if type(e).__name__ in ("TransactionNotFound", "TimeExhausted"):
                return None
            logger.error("Failed to retrieve tx %s: %s", txn_hash, type(e).__name__)
            raise Web3ServiceError(f"Could not read transaction: {type(e).__name__}") from e

        return {
            "hash": normalize_tx_hash(_get(txn, "hash")),
            "input_data": "0x" + decode_input_data(_get(txn, "input")).hex(),
            "block_number": _get(txn, "blockNumber"),
            "status": _get(receipt, "status"),
            "from": _get(txn, "from"),
            "to": _get(txn, "to"),
        }

    def verify_data_hash(self, txn_hash, expected_hash):
        """
        Verify that the hash stored on-chain matches the expected hash, in a mined,
        successful transaction sent by the configured wallet.
        """
        txn = self.get_transaction(txn_hash)
        if not txn:
            return _not_found(expected_hash)

        stored_data = decode_input_data(txn["input_data"])
        try:
            stored_hash = stored_data.decode("utf-8")
        except UnicodeDecodeError:
            stored_hash = stored_data.hex()

        result = {
            "verified": False,
            "found": True,
            "stored_hash": stored_hash,
            "expected_hash": expected_hash,
            "block_number": txn["block_number"],
        }
        if txn["block_number"] is None:
            result["reason"] = "Transaction not yet mined"
        elif txn["status"] != 1:
            result["reason"] = "Transaction failed on-chain"
        elif str(txn.get("from") or "").lower() != str(self.wallet_address).lower():
            result["reason"] = "Transaction not sent by the configured wallet"
        elif stored_hash != expected_hash:
            result["reason"] = "Hash mismatch"
        else:
            result["verified"] = True
            result["reason"] = "Match"
        return result


# ---------------------------------------------------------------------------
# Factory — returns the right implementation
# ---------------------------------------------------------------------------

_service_instance = None


def get_web3_service():
    """
    Return the shared Web3 service.

    BLOCKCHAIN_MOCK_MODE=True  -> MockWeb3Service.
    BLOCKCHAIN_MOCK_MODE=False -> LiveWeb3Service. If it cannot start, Web3ServiceError
    is raised; nothing is silently anchored to the mock ledger. Only with DEBUG=True
    (local development) does it fall back to the mock, logged at ERROR level.
    Failures are not cached, so the next call retries the connection.
    """
    global _service_instance
    if _service_instance is not None:
        return _service_instance

    if getattr(settings, "BLOCKCHAIN_MOCK_MODE", True):
        logger.info("Blockchain running in MOCK mode.")
        _service_instance = MockWeb3Service()
        return _service_instance

    try:
        _service_instance = LiveWeb3Service()
    except (Web3ServiceError, ImportError) as e:
        if not settings.DEBUG:
            logger.error("Live blockchain unavailable (no mock fallback outside DEBUG): %s", e)
            raise Web3ServiceError(str(e)) from e
        logger.error("Live blockchain unavailable; DEBUG is on, so falling back to MOCK mode: %s", e)
        return MockWeb3Service()  # not cached: retry live on the next call

    return _service_instance


def reset_web3_service():
    """Reset the singleton (useful for testing)."""
    global _service_instance
    _service_instance = None
