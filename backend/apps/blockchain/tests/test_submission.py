"""
Live submission hardening: idempotency, nonce management and gas/fee limits.
All against the in-memory fake node (tests/fakes.py) - no network, no funds.
"""
import hashlib

import pytest

from apps.blockchain.models import BlockchainSubmission, BlockchainWallet
from apps.blockchain.services.web3_service import LiveWeb3Service, Web3ServiceError

from .fakes import GWEI, WALLET, FakeW3, RPCError

pytestmark = pytest.mark.django_db
S = BlockchainSubmission.Status


def h(label):
    return hashlib.sha256(label.encode()).hexdigest()


@pytest.fixture(autouse=True)
def _wallet(settings, monkeypatch):
    settings.BLOCKCHAIN_WALLET_ADDRESS = WALLET
    settings.BLOCKCHAIN_GAS_LIMIT_MULTIPLIER = 1.2
    settings.BLOCKCHAIN_MAX_GAS = 100_000
    settings.BLOCKCHAIN_MIN_PRIORITY_FEE_GWEI = 30
    settings.BLOCKCHAIN_MAX_FEE_PER_GAS_GWEI = 500
    settings.BLOCKCHAIN_RECEIPT_TIMEOUT = 5
    monkeypatch.setenv("BLOCKCHAIN_WALLET_PRIVATE_KEY", "0x" + "ab" * 32)


def svc(**kwargs):
    return LiveWeb3Service(w3=FakeW3(**kwargs))


# --- idempotency ------------------------------------------------------------------

def test_same_hash_submitted_twice_creates_one_transaction():
    s = svc()
    first = s.submit_data_hash(h("doc"))
    second = s.submit_data_hash(h("doc"))
    assert first == second
    assert len(s.w3.eth.accepted) == 1
    assert len(s.w3.eth.signed) == 1
    assert BlockchainSubmission.objects.get().status == S.CONFIRMED


def test_receipt_timeout_then_retry_does_not_rebroadcast_a_new_transaction():
    s = svc(auto_mine=False)
    with pytest.raises(Web3ServiceError, match="stays pending"):
        s.submit_data_hash(h("doc"))

    sub = BlockchainSubmission.objects.get()
    assert sub.status == S.BROADCAST
    assert len(s.w3.eth.accepted) == 1

    # Celery retry while still pending: same tx again, still not mined.
    with pytest.raises(Web3ServiceError):
        s.submit_data_hash(h("doc"))
    assert len(s.w3.eth.signed) == 1, "must not sign a second transaction"
    assert len(s.w3.eth.accepted) == 1

    s.w3.eth.mine()
    assert s.submit_data_hash(h("doc")) == sub.txn_hash
    assert BlockchainSubmission.objects.get().status == S.CONFIRMED
    assert len(s.w3.eth.accepted) == 1


def test_retry_after_timeout_from_a_fresh_worker_process():
    """A different worker (new service instance, same DB) resumes the same tx."""
    node = FakeW3(auto_mine=False)
    with pytest.raises(Web3ServiceError):
        LiveWeb3Service(w3=node).submit_data_hash(h("doc"))
    node.eth.mine()

    txn_hash = LiveWeb3Service(w3=node).submit_data_hash(h("doc"))
    assert txn_hash == BlockchainSubmission.objects.get().txn_hash
    assert len(node.eth.signed) == 1


def test_broadcast_error_then_retry_resends_identical_bytes():
    s = svc()
    s.w3.eth.send_error = ConnectionError("RPC timeout")
    with pytest.raises(Web3ServiceError, match="Broadcast failed"):
        s.submit_data_hash(h("doc"))
    sub = BlockchainSubmission.objects.get()
    assert sub.status == S.SIGNED

    assert s.submit_data_hash(h("doc")) == sub.txn_hash
    assert len(s.w3.eth.signed) == 1
    assert BlockchainSubmission.objects.get().broadcast_attempts == 2


def test_already_known_response_counts_as_broadcast():
    s = svc(auto_mine=False, already_known_error=True)
    with pytest.raises(Web3ServiceError):
        s.submit_data_hash(h("doc"))
    s.w3.eth.mine()
    assert s.submit_data_hash(h("doc")) == BlockchainSubmission.objects.get().txn_hash


def test_reverted_transaction_marks_failed_and_next_attempt_uses_new_nonce():
    s = svc(receipt_status=0)
    with pytest.raises(Web3ServiceError, match="reverted"):
        s.submit_data_hash(h("doc"))
    failed = BlockchainSubmission.objects.get()
    assert failed.status == S.FAILED

    s.w3.eth.receipt_status = 1
    txn_hash = s.submit_data_hash(h("doc"))
    new = BlockchainSubmission.objects.get(txn_hash=txn_hash)
    assert new.status == S.CONFIRMED
    assert new.nonce == failed.nonce + 1


def test_nonce_consumed_externally_is_replaced_and_reallocated():
    s = svc()
    s.w3.eth.send_error = ConnectionError("lost before broadcast")
    with pytest.raises(Web3ServiceError):
        s.submit_data_hash(h("doc"))
    stuck = BlockchainSubmission.objects.get()

    s.w3.eth.take_nonce_externally(stuck.nonce)  # e.g. a manual transfer from the wallet
    txn_hash = s.submit_data_hash(h("doc"))

    stuck.refresh_from_db()
    assert stuck.status == S.REPLACED
    new = BlockchainSubmission.objects.get(txn_hash=txn_hash)
    assert new.status == S.CONFIRMED
    assert new.nonce > stuck.nonce


def test_lost_earlier_transaction_is_rebroadcast_to_fill_nonce_gap():
    s = svc(auto_mine=False)
    s.w3.eth.send_error = ConnectionError("worker died mid-broadcast")
    with pytest.raises(Web3ServiceError):
        s.submit_data_hash(h("first"))
    gap = BlockchainSubmission.objects.get()
    assert gap.status == S.SIGNED and len(s.w3.eth.accepted) == 0

    with pytest.raises(Web3ServiceError):  # still pending (auto_mine off)
        s.submit_data_hash(h("second"))

    accepted = {bytes(x) for x in s.w3.eth.accepted}
    assert bytes.fromhex(gap.txn_hash[2:]) in accepted, "earlier nonce must be re-sent"
    assert BlockchainSubmission.objects.get(pk=gap.pk).status == S.BROADCAST


# --- nonces ------------------------------------------------------------------------

def test_nonces_are_sequential_even_when_node_pending_count_lags():
    s = svc(stale_pending_nonce=True)  # node keeps answering 0
    for i in range(5):
        s.submit_data_hash(h(f"doc-{i}"))
    nonces = list(BlockchainSubmission.objects.order_by("nonce").values_list("nonce", flat=True))
    assert nonces == [0, 1, 2, 3, 4]
    assert BlockchainWallet.objects.get().next_nonce == 5


def test_nonce_follows_node_when_wallet_used_elsewhere():
    s = svc()
    s.submit_data_hash(h("a"))
    for n in (1, 2, 3):
        s.w3.eth.take_nonce_externally(n)
    s.submit_data_hash(h("b"))
    assert BlockchainSubmission.objects.get(data_hash=h("b")).nonce == 4


def test_wallet_row_is_per_chain_and_lowercase():
    s = svc()
    s.submit_data_hash(h("a"))
    wallet = BlockchainWallet.objects.get()
    assert wallet.address == WALLET.lower()
    assert wallet.chain_id == 80002


# --- gas & fees ----------------------------------------------------------------------

def test_gas_limit_is_estimate_times_multiplier():
    s = svc(gas_estimate=22_024)
    s.submit_data_hash(h("a"))
    tx = s.w3.eth.signed[0]
    assert tx["gas"] == 26_429  # ceil(22_024 * 1.2)
    assert tx["gas"] != 25_000
    estimate = s.w3.eth.estimate_calls[0]
    assert estimate["data"] == h("a").encode()
    assert estimate["from"] == estimate["to"]


def test_estimate_above_max_gas_is_refused_and_consumes_no_nonce(settings):
    settings.BLOCKCHAIN_MAX_GAS = 25_000
    s = svc(gas_estimate=22_024)
    with pytest.raises(Web3ServiceError, match="BLOCKCHAIN_MAX_GAS"):
        s.submit_data_hash(h("a"))
    assert BlockchainSubmission.objects.count() == 0
    assert s.w3.eth.signed == []
    assert BlockchainWallet.objects.get().next_nonce == 0


def test_eip1559_fees_use_priority_floor():
    s = svc(base_fee=10 * GWEI, suggested_tip=2 * GWEI)  # node suggests less than Polygon's floor
    s.submit_data_hash(h("a"))
    tx = s.w3.eth.signed[0]
    assert tx["type"] == 2
    assert tx["maxPriorityFeePerGas"] == 30 * GWEI
    assert tx["maxFeePerGas"] == 2 * 10 * GWEI + 30 * GWEI
    assert "gasPrice" not in tx


def test_node_tip_used_when_above_floor():
    s = svc(base_fee=10 * GWEI, suggested_tip=45 * GWEI)
    s.submit_data_hash(h("a"))
    assert s.w3.eth.signed[0]["maxPriorityFeePerGas"] == 45 * GWEI


def test_fee_spike_above_cap_is_refused_not_overpaid(settings):
    settings.BLOCKCHAIN_MAX_FEE_PER_GAS_GWEI = 100
    s = svc(base_fee=80 * GWEI)  # 2*80 + 30 = 190 gwei > 100
    with pytest.raises(Web3ServiceError, match="cap"):
        s.submit_data_hash(h("a"))
    assert s.w3.eth.signed == []
    assert BlockchainSubmission.objects.count() == 0


def test_legacy_chain_uses_capped_gas_price(settings):
    s = svc(legacy=True, gas_price=40 * GWEI)
    s.submit_data_hash(h("a"))
    tx = s.w3.eth.signed[0]
    assert tx["gasPrice"] == 40 * GWEI
    assert "maxFeePerGas" not in tx

    settings.BLOCKCHAIN_MAX_FEE_PER_GAS_GWEI = 10
    with pytest.raises(Web3ServiceError, match="cap"):
        s.submit_data_hash(h("b"))


def test_gas_estimation_failure_is_a_service_error():
    s = svc()
    s.w3.eth.estimate_gas = lambda tx: (_ for _ in ()).throw(RPCError("execution reverted"))
    with pytest.raises(Web3ServiceError, match="Gas estimation failed"):
        s.submit_data_hash(h("a"))


# --- secrets ----------------------------------------------------------------------------

def test_private_key_never_persisted_or_logged(caplog):
    key = "0x" + "ab" * 32
    s = svc(auto_mine=False)
    with caplog.at_level("DEBUG"):
        with pytest.raises(Web3ServiceError):
            s.submit_data_hash(h("a"))
    sub = BlockchainSubmission.objects.get()
    for value in (sub.raw_transaction, sub.last_error, sub.txn_hash, caplog.text):
        assert key[2:] not in value


# --- broadcast errors are judged by chain state, not by message wording ----------------

def test_resend_error_with_unfamiliar_wording_for_our_mined_tx_is_success():
    s = svc()
    s.submit_data_hash(h("doc"))
    sub = BlockchainSubmission.objects.get()
    s.w3.eth.send_error = RPCError("Invalid transaction nonce: Expected 1, but got 0")
    assert s._send_raw(sub) is True
    assert BlockchainSubmission.objects.get().status == S.CONFIRMED


def test_unknown_broadcast_error_with_free_nonce_is_retried_not_replaced():
    s = svc()
    s.w3.eth.send_error = RPCError("insufficient funds for gas * price + value")
    with pytest.raises(Web3ServiceError, match="Broadcast failed"):
        s.submit_data_hash(h("doc"))
    sub = BlockchainSubmission.objects.get()
    assert sub.status == S.SIGNED
    assert sub.last_error == "RPCError"


def test_rpc_and_signing_errors_become_retryable_service_errors():
    s = svc()
    s.w3.eth.get_transaction_count = lambda *a, **k: (_ for _ in ()).throw(ConnectionError("rpc down"))
    with pytest.raises(Web3ServiceError, match="Nonce lookup failed"):
        s.submit_data_hash(h("a"))

    s = svc()
    s.w3.eth.sign_transaction = lambda tx, key: (_ for _ in ()).throw(ValueError(f"bad key {key}"))
    with pytest.raises(Web3ServiceError, match="Signing failed") as exc:
        s.submit_data_hash(h("a"))
    assert "ab" * 32 not in str(exc.value)
    assert exc.value.__cause__ is None  # the original (key-bearing) error is not chained
    assert BlockchainSubmission.objects.count() == 0
