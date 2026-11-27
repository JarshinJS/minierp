"""
H1 regression: with BLOCKCHAIN_MOCK_MODE=False, a live-service failure (bad provider
URL, web3 not installed, node down) silently swapped in the mock service. In
production that means documents get "anchored" to a fake chain without anyone
noticing. The fallback is now refused unless DEBUG is on.
"""
import logging

import pytest

from apps.blockchain.models import BlockchainDocument
from apps.blockchain.services import web3_service
from apps.blockchain.services.verification_service import register_document, verify_document
from apps.blockchain.services.web3_service import (
    LiveWeb3Service,
    MockWeb3Service,
    Web3ServiceError,
    get_web3_service,
)
from apps.foreign_trade.models import DocumentVerificationStatus


@pytest.fixture
def live_mode_broken(settings, monkeypatch):
    settings.BLOCKCHAIN_MOCK_MODE = False
    settings.DEBUG = False

    def boom(self, w3=None):
        raise Web3ServiceError("Cannot connect to Web3 provider")

    monkeypatch.setattr(LiveWeb3Service, "__init__", boom)


def test_mock_mode_returns_mock(settings):
    settings.BLOCKCHAIN_MOCK_MODE = True
    assert isinstance(get_web3_service(), MockWeb3Service)


def test_singleton(settings):
    settings.BLOCKCHAIN_MOCK_MODE = True
    assert get_web3_service() is get_web3_service()


def test_production_live_failure_raises_instead_of_falling_back(live_mode_broken):
    with pytest.raises(Web3ServiceError):
        get_web3_service()


def test_production_live_failure_is_not_cached(live_mode_broken, monkeypatch):
    with pytest.raises(Web3ServiceError):
        get_web3_service()

    sentinel = object()
    monkeypatch.setattr(web3_service, "LiveWeb3Service", lambda: sentinel)
    assert get_web3_service() is sentinel


def test_debug_live_failure_falls_back_loudly(live_mode_broken, settings, caplog):
    settings.DEBUG = True
    with caplog.at_level(logging.ERROR, logger=web3_service.__name__):
        svc = get_web3_service()
    assert isinstance(svc, MockWeb3Service)
    assert "MOCK" in caplog.text


@pytest.mark.django_db
def test_register_document_fails_without_writing_records(live_mode_broken, trade_document):
    with pytest.raises(Web3ServiceError):
        register_document(trade_document)

    trade_document.refresh_from_db()
    assert BlockchainDocument.objects.count() == 0
    assert trade_document.verification_status == DocumentVerificationStatus.PENDING


@pytest.mark.django_db
def test_verify_document_when_chain_unavailable_does_not_flag_tampered(settings, trade_document, monkeypatch):
    settings.BLOCKCHAIN_MOCK_MODE = True
    register_document(trade_document)
    web3_service.reset_web3_service()

    def unavailable():
        raise Web3ServiceError("node down")

    monkeypatch.setattr("apps.blockchain.services.verification_service.get_web3_service", unavailable)
    result = verify_document(trade_document)

    trade_document.refresh_from_db()
    assert result["verified"] is False
    assert trade_document.verification_status == DocumentVerificationStatus.VERIFIED  # unchanged
    assert "unavailable" in result["message"].lower()


@pytest.mark.django_db
def test_dashboard_renders_when_live_chain_unavailable(live_mode_broken, client, user):
    client.force_login(user)
    response = client.get("/blockchain/")
    assert response.status_code == 200
    assert response.context["is_connected"] is False
    assert response.context["network_info"]["is_mock"] is False
