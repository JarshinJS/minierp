"""
Hashing and document/audit verification against the (persistent) mock chain.

Ported from the old apps/blockchain/tests.py, which could never be collected: it was
shadowed by this tests/ package and imported APIs that no longer exist
(Web3Service, anchor_document_to_blockchain, AuditEventTypes).
"""
from django.core.files.base import ContentFile

import pytest

from apps.blockchain.models import BlockchainAuditLog, BlockchainDocument
from apps.blockchain.services.hashing_service import generate_data_hash, generate_file_hash
from apps.blockchain.services.verification_service import (
    log_audit_event,
    register_document,
    verify_audit_event,
    verify_document,
)
from apps.blockchain.services.web3_service import MockWeb3Service
from apps.foreign_trade.models import DocumentVerificationStatus

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _mock_mode(settings):
    settings.BLOCKCHAIN_MOCK_MODE = True


# --- hashing (ported) ------------------------------------------------------------

def test_generate_file_hash():
    mock_file = type("MockFile", (), {"read": lambda self, n=-1: b""})()
    assert len(generate_file_hash(b"hello world")) == 64
    assert len(generate_file_hash(mock_file)) == 64


def test_generate_data_hash_is_canonical():
    assert generate_data_hash({"a": 1, "b": 2}) == generate_data_hash({"b": 2, "a": 1})
    assert len(generate_data_hash({"test": "data", "value": 123})) == 64


def test_mock_mode_anchor():
    svc = MockWeb3Service()
    txn_hash = svc.submit_data_hash("testhash")
    assert txn_hash.startswith("0x")
    assert svc.get_network_info()["is_mock"] is True
    assert svc.get_transaction(txn_hash)["block_number"] > 0


# --- documents -----------------------------------------------------------------------

def test_register_document(trade_document):
    bc_doc = register_document(trade_document)

    trade_document.refresh_from_db()
    assert bc_doc.document_hash == generate_file_hash(trade_document.file)
    assert bc_doc.blockchain_txn.startswith("0x")
    assert bc_doc.block_number
    assert bc_doc.verified is True
    assert trade_document.verification_status == DocumentVerificationStatus.VERIFIED


def test_register_document_is_idempotent(trade_document):
    first = register_document(trade_document)
    second = register_document(trade_document)
    assert first.pk == second.pk
    assert BlockchainDocument.objects.count() == 1


def test_verify_document_success(trade_document):
    register_document(trade_document)
    result = verify_document(trade_document)
    assert result["verified"] is True
    assert result["status"] == DocumentVerificationStatus.VERIFIED


def test_verify_document_tampered_file(trade_document):
    register_document(trade_document)
    trade_document.file.save("invoice.pdf", ContentFile(b"forged content"), save=True)

    result = verify_document(trade_document)

    trade_document.refresh_from_db()
    assert result["verified"] is False
    assert trade_document.verification_status == DocumentVerificationStatus.TAMPERED


def test_verify_document_tampered_db_hash(trade_document):
    bc_doc = register_document(trade_document)
    BlockchainDocument.objects.filter(pk=bc_doc.pk).update(document_hash="0" * 64)

    result = verify_document(trade_document)
    assert result["verified"] is False
    assert result["status"] == DocumentVerificationStatus.TAMPERED


def test_verify_document_missing_on_chain_is_unverified_not_tampered(trade_document):
    bc_doc = register_document(trade_document)
    BlockchainDocument.objects.filter(pk=bc_doc.pk).update(blockchain_txn="0x" + "0" * 64)

    result = verify_document(trade_document)
    assert result["verified"] is False
    assert result["status"] == DocumentVerificationStatus.UNVERIFIED


def test_verify_document_pending_registration(trade_document):
    result = verify_document(trade_document)
    trade_document.refresh_from_db()
    assert result["verified"] is False
    assert trade_document.verification_status == DocumentVerificationStatus.PENDING


# --- audit events ----------------------------------------------------------------------

def test_log_and_verify_audit_event(user):
    log = log_audit_event("ORDER_CREATED", "abc", "ExportOrder", user=user, metadata={"n": "EXP-1"})
    assert BlockchainAuditLog.objects.count() == 1
    assert verify_audit_event(log)["verified"] is True


def test_audit_event_tampered_metadata(user):
    log = log_audit_event("ORDER_CREATED", "abc", "ExportOrder", user=user, metadata={"n": "EXP-1"})
    log.metadata = {"n": "EXP-2"}
    assert verify_audit_event(log)["verified"] is False
