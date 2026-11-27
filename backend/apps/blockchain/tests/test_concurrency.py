"""
Concurrency: several workers (threads with their own DB connections) submitting
through one wallet must never sign two transactions with the same nonce, and
concurrent submissions of the same hash must produce exactly one transaction.

The fake node rejects a second transaction for a used nonce, exactly as Polygon
nodes do, and is configured with a lagging pending count so only the database
nonce lock can keep workers apart.
"""
import hashlib
import threading

import pytest
from django.db import connection, connections

from apps.blockchain.models import BlockchainSubmission, BlockchainWallet
from apps.blockchain.services.web3_service import LiveWeb3Service, Web3ServiceError

from .fakes import WALLET, FakeW3

WORKERS = 8


@pytest.fixture(autouse=True)
def _wallet(settings, monkeypatch):
    settings.BLOCKCHAIN_WALLET_ADDRESS = WALLET
    settings.BLOCKCHAIN_RECEIPT_TIMEOUT = 5
    monkeypatch.setenv("BLOCKCHAIN_WALLET_PRIVATE_KEY", "0x" + "ab" * 32)


def _run_concurrently(fn, n):
    barrier = threading.Barrier(n)
    results, errors = [None] * n, []

    def worker(i):
        try:
            barrier.wait()
            results[i] = fn(i)
        except Exception as e:  # collected and asserted on below
            errors.append(e)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    return results, errors


def _skip_if_db_cannot_share():
    if connection.vendor == "sqlite" and connection.is_in_memory_db():
        pytest.skip("in-memory SQLite fails instead of waiting on locks; see backend/conftest.py")


@pytest.mark.django_db(transaction=True)
def test_concurrent_workers_get_unique_sequential_nonces():
    _skip_if_db_cannot_share()
    node = FakeW3(stale_pending_nonce=True)  # node always says "next nonce is 0"
    # Create the wallet row up front, as the first real submission would.
    BlockchainWallet.objects.create(address=WALLET.lower(), chain_id=node.eth.chain_id)

    def submit(i):
        return LiveWeb3Service(w3=node).submit_data_hash(hashlib.sha256(f"doc-{i}".encode()).hexdigest())

    results, errors = _run_concurrently(submit, WORKERS)

    assert errors == []
    nonces = sorted(BlockchainSubmission.objects.values_list("nonce", flat=True))
    assert nonces == list(range(WORKERS))
    assert len(set(results)) == WORKERS
    assert len(node.eth.accepted) == WORKERS          # node accepted every one: no collisions
    assert set(BlockchainSubmission.objects.values_list("status", flat=True)) == {"CONFIRMED"}
    assert BlockchainWallet.objects.get().next_nonce == WORKERS


@pytest.mark.django_db(transaction=True)
def test_concurrent_submissions_of_same_hash_create_one_transaction():
    _skip_if_db_cannot_share()
    node = FakeW3()
    BlockchainWallet.objects.create(address=WALLET.lower(), chain_id=node.eth.chain_id)
    data_hash = hashlib.sha256(b"same document").hexdigest()

    results, errors = _run_concurrently(lambda i: LiveWeb3Service(w3=node).submit_data_hash(data_hash), WORKERS)

    assert errors == []
    assert len(set(results)) == 1
    assert BlockchainSubmission.objects.count() == 1
    assert len(node.eth.signed) == 1
    assert len(node.eth.accepted) == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_workers_with_receipt_timeouts_never_duplicate():
    """Workers time out, retry, and time out again; the ledger still holds one tx per hash."""
    _skip_if_db_cannot_share()
    node = FakeW3(auto_mine=False)
    BlockchainWallet.objects.create(address=WALLET.lower(), chain_id=node.eth.chain_id)
    hashes = [hashlib.sha256(f"doc-{i % 3}".encode()).hexdigest() for i in range(WORKERS)]

    def attempt(i):
        for _ in range(2):  # initial run + one Celery retry, both time out
            try:
                LiveWeb3Service(w3=node).submit_data_hash(hashes[i])
            except Web3ServiceError:
                pass

    _, errors = _run_concurrently(attempt, WORKERS)
    assert errors == []
    node.eth.mine()

    assert BlockchainSubmission.objects.count() == 3
    assert len(node.eth.signed) == 3
    assert len(node.eth.accepted) == 3
    assert sorted(BlockchainSubmission.objects.values_list("nonce", flat=True)) == [0, 1, 2]
