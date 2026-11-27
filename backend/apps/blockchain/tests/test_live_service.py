"""
H1 regression: live (Web3) transaction hash decoding and on-chain verification.

web3 v7 depends on hexbytes>=1.0, whose HexBytes.hex() returns hex *without* the
"0x" prefix. The service stored that unprefixed string as the transaction hash, and
JSON-RPC nodes reject unprefixed hashes, so every later lookup failed and was
reported as "Transaction not found". Verification also ignored the receipt status
(reverted transactions counted as anchored) and the sender.

A small in-memory fake stands in for ``web3.Web3`` so these tests run without a
node (or the web3 package) installed.
"""
import hashlib

import pytest

from apps.blockchain.services.web3_service import (
    LiveWeb3Service,
    Web3ServiceError,
    decode_input_data,
    normalize_tx_hash,
)

from .fakes import OTHER, WALLET, FakeW3, HexBytes, LegacyHexBytes
from .fakes import key as _key

# Submissions are persisted (nonce + idempotency bookkeeping).
pytestmark = pytest.mark.django_db

DOC_HASH = hashlib.sha256(b"document").hexdigest()


@pytest.fixture(autouse=True)
def _wallet(settings, monkeypatch):
    settings.BLOCKCHAIN_WALLET_ADDRESS = WALLET
    settings.BLOCKCHAIN_NETWORK_NAME = "polygon-amoy"
    monkeypatch.setenv("BLOCKCHAIN_WALLET_PRIVATE_KEY", "0x" + "ab" * 32)


def _service(**kwargs):
    return LiveWeb3Service(w3=FakeW3(**kwargs))


# --- transaction hash decoding ---------------------------------------------------

@pytest.mark.parametrize("hexbytes_cls", [HexBytes, LegacyHexBytes])
def test_submit_returns_0x_prefixed_hash(hexbytes_cls):
    txn_hash = _service(hexbytes_cls=hexbytes_cls).submit_data_hash(DOC_HASH)
    assert txn_hash.startswith("0x")
    assert len(txn_hash) == 66


@pytest.mark.parametrize("hexbytes_cls", [HexBytes, LegacyHexBytes])
def test_submitted_hash_round_trips_through_verification(hexbytes_cls):
    svc = _service(hexbytes_cls=hexbytes_cls)
    txn_hash = svc.submit_data_hash(DOC_HASH)

    result = svc.verify_data_hash(txn_hash, DOC_HASH)

    assert result["verified"] is True, result
    assert result["stored_hash"] == DOC_HASH


def test_get_transaction_reports_block_and_prefixed_fields():
    svc = _service()
    txn_hash = svc.submit_data_hash(DOC_HASH)
    txn = svc.get_transaction(txn_hash)
    assert txn["hash"] == txn_hash
    assert txn["input_data"].startswith("0x")
    assert txn["block_number"] > 0
    assert txn["status"] == 1


def test_legacy_unprefixed_hash_in_db_still_verifies():
    """Records written by the buggy version stored hashes without 0x."""
    svc = _service()
    txn_hash = svc.submit_data_hash(DOC_HASH)
    assert svc.verify_data_hash(txn_hash[2:], DOC_HASH)["verified"] is True


# --- verification rules ------------------------------------------------------------

def test_hash_mismatch_not_verified():
    svc = _service()
    txn_hash = svc.submit_data_hash(DOC_HASH)
    result = svc.verify_data_hash(txn_hash, "f" * 64)
    assert result["verified"] is False
    assert result["reason"] == "Hash mismatch"


def test_reverted_transaction_not_verified():
    svc = _service()
    txn_hash = svc.submit_data_hash(DOC_HASH)
    svc.w3.eth.receipts[_key(txn_hash)]["status"] = 0
    result = svc.verify_data_hash(txn_hash, DOC_HASH)
    assert result["verified"] is False
    assert result["reason"] == "Transaction failed on-chain"


def test_transaction_from_other_sender_not_verified():
    svc = _service(sender=OTHER)
    txn_hash = svc.submit_data_hash(DOC_HASH)
    result = svc.verify_data_hash(txn_hash, DOC_HASH)
    assert result["verified"] is False
    assert result["reason"] == "Transaction not sent by the configured wallet"


def test_unknown_transaction_not_found():
    result = _service().verify_data_hash("0x" + "00" * 32, DOC_HASH)
    assert result == {"verified": False, "found": False, "reason": "Transaction not found",
                      "expected_hash": DOC_HASH, "stored_hash": None}


def test_rpc_error_is_raised_not_reported_as_missing():
    svc = _service()
    txn_hash = svc.submit_data_hash(DOC_HASH)
    svc.w3.eth.rpc_error = ConnectionError("node down")
    with pytest.raises(Web3ServiceError):
        svc.verify_data_hash(txn_hash, DOC_HASH)


def test_submit_raises_when_receipt_reverted():
    with pytest.raises(Web3ServiceError, match="reverted"):
        _service(receipt_status=0).submit_data_hash(DOC_HASH)


def test_submit_requires_private_key(monkeypatch):
    monkeypatch.delenv("BLOCKCHAIN_WALLET_PRIVATE_KEY")
    with pytest.raises(Web3ServiceError, match="PRIVATE_KEY"):
        _service().submit_data_hash(DOC_HASH)


def test_network_info_is_not_mock():
    info = _service().get_network_info()
    assert info == {"chain_id": 80002, "network_name": "polygon-amoy", "is_mock": False}


# --- helpers -----------------------------------------------------------------------

@pytest.mark.parametrize("value, expected", [
    (b"\x00\xab", "0x00ab"),
    (HexBytes(b"\x00\xab"), "0x00ab"),
    (LegacyHexBytes(b"\x00\xab"), "0x00ab"),
    ("00AB", "0x00ab"),
    ("0x00ab", "0x00ab"),
    ("0X00AB", "0x00ab"),
])
def test_normalize_tx_hash(value, expected):
    assert normalize_tx_hash(value) == expected


@pytest.mark.parametrize("value, expected", [
    ("0x3030", b"00"),          # leading '0' digits must not be stripped (old lstrip("0x") bug)
    ("0x003030", b"\x0000"),
    ("3030", b"00"),
    (HexBytes(b"00"), b"00"),
    (LegacyHexBytes(b"00"), b"00"),
    ("", b""),
    (None, b""),
    ("0x", b""),
])
def test_decode_input_data(value, expected):
    assert decode_input_data(value) == expected
