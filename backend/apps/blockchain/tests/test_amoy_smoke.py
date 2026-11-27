"""
Opt-in live smoke test against Polygon **Amoy testnet** (chain id 80002).

Skipped unless explicitly enabled. It sends one real (testnet) transaction:

    MINIERP_AMOY_SMOKE=1 \\
    WEB3_PROVIDER_URL=...  BLOCKCHAIN_WALLET_ADDRESS=0x...  BLOCKCHAIN_WALLET_PRIVATE_KEY=... \\
    pytest apps/blockchain/tests/test_amoy_smoke.py

Credentials are read from the environment only and are never printed. The test
refuses to run on any chain other than Amoy, so it can't spend real funds.
"""
import hashlib
import os
import time

import pytest

AMOY_CHAIN_ID = 80002

pytestmark = [
    pytest.mark.skipif(os.getenv("MINIERP_AMOY_SMOKE") != "1", reason="set MINIERP_AMOY_SMOKE=1 to run"),
    pytest.mark.django_db,
]


@pytest.fixture
def live_service(settings):
    pytest.importorskip("web3")
    for var in ("WEB3_PROVIDER_URL", "BLOCKCHAIN_WALLET_ADDRESS", "BLOCKCHAIN_WALLET_PRIVATE_KEY"):
        if not os.getenv(var):
            pytest.skip(f"{var} is not set")
    settings.BLOCKCHAIN_MOCK_MODE = False
    settings.WEB3_PROVIDER_URL = os.environ["WEB3_PROVIDER_URL"]
    settings.BLOCKCHAIN_WALLET_ADDRESS = os.environ["BLOCKCHAIN_WALLET_ADDRESS"]
    settings.BLOCKCHAIN_NETWORK_NAME = "polygon-amoy"
    settings.BLOCKCHAIN_RECEIPT_TIMEOUT = 180

    from apps.blockchain.services.web3_service import LiveWeb3Service

    svc = LiveWeb3Service()
    if svc.chain_id != AMOY_CHAIN_ID:
        pytest.fail(f"Refusing to run: chain id {svc.chain_id} is not Polygon Amoy ({AMOY_CHAIN_ID}).")
    return svc


def test_anchor_and_verify_on_amoy(live_service):
    from apps.blockchain.models import BlockchainSubmission

    data_hash = hashlib.sha256(f"minierp-amoy-smoke-{time.time_ns()}".encode()).hexdigest()

    txn_hash = live_service.submit_data_hash(data_hash)
    assert txn_hash.startswith("0x") and len(txn_hash) == 66

    # Idempotent: a second call returns the same transaction without sending another.
    assert live_service.submit_data_hash(data_hash) == txn_hash
    assert BlockchainSubmission.objects.filter(data_hash=data_hash).count() == 1

    result = live_service.verify_data_hash(txn_hash, data_hash)
    assert result["verified"] is True, result["reason"]
    assert live_service.verify_data_hash(txn_hash, "0" * 64)["verified"] is False
