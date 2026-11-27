from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from apps.blockchain.services.web3_service import reset_web3_service


@pytest.fixture(autouse=True)
def _fresh_web3_singleton():
    """Every test starts without a cached Web3 service (no cross-test leakage)."""
    reset_web3_service()
    yield
    reset_web3_service()


@pytest.fixture(autouse=True)
def _media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(email="bc@test.com", password="pw-123456", role="ADMIN")


@pytest.fixture
def export_order(user):
    from apps.foreign_trade.models import Country, Currency, Incoterm, TradeCustomer
    from apps.foreign_trade.services import create_export_order

    country = Country.objects.create(name="USA", code="US")
    currency = Currency.objects.create(code="USD", name="US Dollar", symbol="$", exchange_rate=Decimal("1.00"))
    incoterm = Incoterm.objects.create(code="FOB", name="Free on Board")
    customer = TradeCustomer.objects.create(name="Global Importers", country=country)
    return create_export_order(
        customer=customer, country=country, currency=currency, incoterm=incoterm,
        lines_data=[{"description": "Item", "quantity": 1, "unit_price": Decimal("10.00")}],
        created_by=user,
    )


@pytest.fixture
def trade_document(export_order, user):
    from apps.foreign_trade.services import upload_document

    return upload_document(
        file=ContentFile(b"commercial invoice v1", name="invoice.pdf"),
        document_type="COMMERCIAL_INVOICE", related_order=export_order,
        uploaded_by=user, title="Invoice",
    )
