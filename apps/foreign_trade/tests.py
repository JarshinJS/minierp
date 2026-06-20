import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from core.exceptions import WorkflowError, DomainError

from apps.foreign_trade.models import (
    Country, Currency, Incoterm, TradeCustomer, TradeSupplier,
    ExportOrder, ExportOrderLine, ImportOrder, ImportOrderLine,
    ExportOrderStatus, ImportOrderStatus, CustomsStatus
)
from apps.foreign_trade.services import (
    create_export_order, confirm_export_order, ship_export_order, deliver_export_order,
    create_import_order, confirm_import_order, transition_import_order_customs
)

User = get_user_model()


@pytest.fixture
def setup_data(db):
    user = User.objects.create_user(email="admin@erp.com", password="password", role="ADMIN")
    country = Country.objects.create(name="USA", code="US")
    currency = Currency.objects.create(code="USD", name="US Dollar", symbol="$", exchange_rate=Decimal("1.00"))
    incoterm = Incoterm.objects.create(code="FOB", name="Free on Board")
    
    customer = TradeCustomer.objects.create(name="Global Importers", country=country)
    supplier = TradeSupplier.objects.create(name="Global Exporters", country=country)
    
    return {
        "user": user,
        "country": country,
        "currency": currency,
        "incoterm": incoterm,
        "customer": customer,
        "supplier": supplier
    }


@pytest.mark.django_db
class TestExportOrderServices:
    def test_create_export_order(self, setup_data):
        lines_data = [
            {"description": "Item 1", "quantity": 10, "unit_price": Decimal("100.00")},
            {"description": "Item 2", "quantity": 5, "unit_price": Decimal("50.00")}
        ]
        
        order = create_export_order(
            customer=setup_data["customer"],
            country=setup_data["country"],
            currency=setup_data["currency"],
            incoterm=setup_data["incoterm"],
            lines_data=lines_data,
            created_by=setup_data["user"]
        )
        
        assert order.status == ExportOrderStatus.DRAFT
        assert order.lines.count() == 2
        assert order.total_amount == Decimal("1250.00")

    def test_confirm_export_order(self, setup_data):
        order = create_export_order(
            customer=setup_data["customer"],
            country=setup_data["country"],
            currency=setup_data["currency"],
            incoterm=setup_data["incoterm"],
            lines_data=[{"description": "Item 1", "quantity": 1, "unit_price": Decimal("100.00")}],
            created_by=setup_data["user"]
        )
        
        confirmed_order = confirm_export_order(order, setup_data["user"])
        assert confirmed_order.status == ExportOrderStatus.CONFIRMED

        with pytest.raises(WorkflowError):
            # Can't confirm twice
            confirm_export_order(confirmed_order, setup_data["user"])


@pytest.mark.django_db
class TestImportOrderServices:
    def test_create_import_order(self, setup_data):
        lines_data = [
            {"description": "Raw Material", "quantity": 100, "unit_price": Decimal("10.00")}
        ]
        
        order = create_import_order(
            supplier=setup_data["supplier"],
            country=setup_data["country"],
            currency=setup_data["currency"],
            lines_data=lines_data,
            created_by=setup_data["user"]
        )
        
        assert order.status == ImportOrderStatus.DRAFT
        assert order.customs_status == CustomsStatus.NOT_STARTED
        assert order.lines.count() == 1
        assert order.total_amount == Decimal("1000.00")

    def test_import_workflow(self, setup_data):
        order = create_import_order(
            supplier=setup_data["supplier"],
            country=setup_data["country"],
            currency=setup_data["currency"],
            lines_data=[{"description": "RM", "quantity": 1, "unit_price": Decimal("10.00")}],
            created_by=setup_data["user"]
        )
        
        # Confirm
        order = confirm_import_order(order, setup_data["user"])
        assert order.status == ImportOrderStatus.CONFIRMED
        
        # Manual change to IN_TRANSIT for test setup
        order.status = ImportOrderStatus.IN_TRANSIT
        order.save()
        
        # Enter Customs
        order = transition_import_order_customs(order, "ENTER_CUSTOMS", setup_data["user"])
        assert order.status == ImportOrderStatus.CUSTOMS
        assert order.customs_status == CustomsStatus.IN_CLEARANCE
        
        # Clear Customs & Receive
        order = transition_import_order_customs(order, "CLEAR", setup_data["user"])
        assert order.status == ImportOrderStatus.RECEIVED
        assert order.customs_status == CustomsStatus.CLEARED
