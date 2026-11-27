"""The demo seed must be repeatable, and its destructive --reset must be impossible
outside the disposable e2e database."""
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.accounts.models import AccountStatus, User, UserRole
from apps.products.models import Product
from apps.sales.models import SalesOrder, SalesOrderStatus
from core.management.commands.seed_demo import DEMO_PASSWORD, DEMO_USERS


@pytest.mark.django_db
def test_reset_refuses_outside_e2e_settings(settings):
    settings.E2E = False
    with pytest.raises(CommandError, match="only runs with --settings=config.settings.e2e"):
        call_command("seed_demo", reset=True)


@pytest.mark.django_db
def test_seed_is_idempotent_and_goes_through_services():
    call_command("seed_demo")
    counts = (User.objects.count(), Product.objects.count(), SalesOrder.objects.count())
    call_command("seed_demo")
    assert (User.objects.count(), Product.objects.count(), SalesOrder.objects.count()) == counts

    for local, _name, role in DEMO_USERS:
        user = User.objects.get(email=f"{local}@demo.minierp.dev")
        assert user.role == role and user.is_approved and user.check_password(DEMO_PASSWORD)
    assert User.objects.get(email="pending@demo.minierp.dev").account_status == AccountStatus.PENDING
    assert User.objects.get(email="admin@demo.minierp.dev").role == UserRole.ADMIN

    # Opening stock is a ledger receipt; confirming an order reserved stock.
    chair = Product.objects.get(sku="FG-CHR")
    assert chair.on_hand_qty == Decimal("48") and chair.reserved_qty == Decimal("12")
    assert chair.ledger_entries.filter(entry_type="RECEIPT", quantity=Decimal("48")).exists()
    assert SalesOrder.objects.filter(status=SalesOrderStatus.CONFIRMED).count() == 2
