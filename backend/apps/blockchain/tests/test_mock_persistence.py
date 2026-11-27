"""
C1 regression: mock-mode transactions used to live in a per-process dict, so any
restart, second gunicorn worker or Celery worker lost them and every verification
afterwards reported "Transaction not found" (and flagged documents as TAMPERED).
"""
import re

import pytest

from apps.blockchain.services.verification_service import register_document, verify_document
from apps.blockchain.services.web3_service import MockWeb3Service, get_web3_service, reset_web3_service
from apps.foreign_trade.models import DocumentVerificationStatus

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _mock_mode(settings):
    settings.BLOCKCHAIN_MOCK_MODE = True


def test_mock_txn_visible_to_another_service_instance():
    txn_hash = MockWeb3Service().submit_data_hash("abc123")

    other_process = MockWeb3Service()
    txn = other_process.get_transaction(txn_hash)

    assert txn is not None
    assert txn["input_data"] == "abc123"
    assert other_process.verify_data_hash(txn_hash, "abc123")["verified"] is True


def test_mock_txn_survives_singleton_reset():
    txn_hash = get_web3_service().submit_data_hash("deadbeef")
    reset_web3_service()  # what a process restart does to the old in-memory store

    result = get_web3_service().verify_data_hash(txn_hash, "deadbeef")
    assert result["verified"] is True, result


def test_mock_detects_hash_mismatch_across_instances():
    txn_hash = MockWeb3Service().submit_data_hash("original")
    result = MockWeb3Service().verify_data_hash(txn_hash, "forged")
    assert result["verified"] is False
    assert result["reason"] == "Hash mismatch"


def test_mock_unknown_txn_not_verified():
    result = MockWeb3Service().verify_data_hash("0x" + "0" * 64, "anything")
    assert result["verified"] is False
    assert result["reason"] == "Transaction not found"


def test_mock_txn_hash_is_32_bytes_hex():
    txn_hash = MockWeb3Service().submit_data_hash("abc")
    assert re.fullmatch(r"0x[0-9a-f]{64}", txn_hash)


def test_mock_block_numbers_increase_across_instances():
    a = MockWeb3Service()
    b = MockWeb3Service()
    first = a.get_transaction(a.submit_data_hash("one"))["block_number"]
    second = b.get_transaction(b.submit_data_hash("two"))["block_number"]
    assert second > first


def test_document_still_verifies_after_restart(trade_document):
    register_document(trade_document)
    reset_web3_service()

    result = verify_document(trade_document)

    trade_document.refresh_from_db()
    assert result["verified"] is True, result
    assert trade_document.verification_status == DocumentVerificationStatus.VERIFIED
