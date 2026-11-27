"""
Foreign-trade "Verify" button / API: each outcome gets its own message.

Before, the HTML partial showed "Tampered" for *any* unverified result, including
"registration still pending" and "blockchain unreachable".
"""
import pytest
from django.core.files.base import ContentFile
from django.urls import reverse

from apps.blockchain.models import BlockchainDocument
from apps.blockchain.services.verification_service import register_document
from apps.blockchain.services.web3_service import Web3ServiceError
from apps.foreign_trade.models import DocumentVerificationStatus

pytestmark = pytest.mark.django_db

LABELS = {
    "VERIFIED": "Verified",
    "TAMPERED": "Tampered",
    "UNVERIFIED": "Unverified",
    "PENDING": "Registration pending",
    "UNAVAILABLE": "Network unavailable",
}


@pytest.fixture(autouse=True)
def _mock_mode(settings):
    settings.BLOCKCHAIN_MOCK_MODE = True


def _arrange(outcome, doc, monkeypatch):
    if outcome == "PENDING":
        return
    bc = register_document(doc)
    if outcome == "TAMPERED":
        doc.file.save("invoice.pdf", ContentFile(b"altered"), save=True)
    elif outcome == "UNVERIFIED":
        BlockchainDocument.objects.filter(pk=bc.pk).update(blockchain_txn="0x" + "0" * 64)
    elif outcome == "UNAVAILABLE":
        def down():
            raise Web3ServiceError("node down")
        monkeypatch.setattr("apps.blockchain.services.verification_service.get_web3_service", down)


@pytest.mark.parametrize("outcome", list(LABELS))
def test_html_partial_shows_distinct_badge(outcome, client, user, trade_document, monkeypatch):
    _arrange(outcome, trade_document, monkeypatch)
    client.force_login(user)

    response = client.post(reverse("foreign_trade:document_verify", args=[trade_document.pk]))

    assert response.status_code == 200
    html = response.content.decode()
    assert response.context["result"]["outcome"] == outcome
    assert LABELS[outcome] in html
    assert response.context["result"]["message"] in html
    if outcome != "TAMPERED":
        assert "Tampered" not in html


@pytest.mark.parametrize("outcome", list(LABELS))
def test_api_reports_outcome(outcome, client, user, trade_document, monkeypatch):
    _arrange(outcome, trade_document, monkeypatch)
    client.force_login(user)

    response = client.post(f"/api/trade/documents/{trade_document.pk}/verify/")

    assert response.status_code == 200, response.content
    body = response.json()
    assert body["outcome"] == outcome
    assert body["verified"] is (outcome == "VERIFIED")


def test_unavailable_leaves_stored_status_untouched(client, user, trade_document, monkeypatch):
    _arrange("UNAVAILABLE", trade_document, monkeypatch)
    client.force_login(user)
    client.post(reverse("foreign_trade:document_verify", args=[trade_document.pk]))
    trade_document.refresh_from_db()
    assert trade_document.verification_status == DocumentVerificationStatus.VERIFIED
