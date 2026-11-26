import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from core.exceptions import DomainError, WorkflowError
from apps.products.models import Product, Category, UnitOfMeasure
from apps.inventory.models import InventoryLedgerEntry, LedgerEntryType
from apps.inventory import services as inventory_services
from apps.sales import services as sales_services
from apps.sales.models import SalesOrderStatus
from apps.delivery.models import DeliveryNote, DeliveryNoteLine, DeliveryNoteStatus
from apps.delivery import services as delivery_services

User = get_user_model()

@pytest.fixture
def delivery_setup(db):
    category = Category.objects.create(name="Furniture")
    product = Product.objects.create(
        name="Oak Table",
        sku="OAK-TBL-01",
        category=category,
        cost_price=Decimal("50.00"),
        selling_price=Decimal("150.00"),
        unit_of_measure=UnitOfMeasure.PCS
    )
    user = User.objects.create_user(
        email="admin@example.com",
        password="password",
        full_name="Admin User",
        role="ADMIN"
    )
    return {"product": product, "user": user}


@pytest.mark.django_db
class TestDeliveryWorkflow:
    def test_delivery_note_workflow(self, delivery_setup):
        product = delivery_setup["product"]
        user = delivery_setup["user"]

        # Receive 10 units in stock
        inventory_services.receive_stock(product, Decimal("10.00"), reference="Receipt")

        # Create sales order for 5 units
        lines_data = [{"product": product, "quantity": Decimal("5.00"), "unit_price": Decimal("150.00")}]
        order = sales_services.create_order("Acme Corp", user, lines_data)
        sales_services.confirm_order(order)

        order.refresh_from_db()
        product.refresh_from_db()
        assert product.reserved_qty == Decimal("5.00")

        # Create Delivery Note
        so_line = order.lines.first()
        lines_data = [{"sales_order_line": so_line, "quantity": Decimal("5.00")}]
        dn = delivery_services.create_delivery_note(order, lines_data, user)

        assert dn.status == DeliveryNoteStatus.PENDING
        assert dn.lines.count() == 1
        assert dn.lines.first().quantity == Decimal("5.00")

        # Dispatch Delivery Note
        delivery_services.dispatch_delivery_note(dn, user)
        dn.refresh_from_db()
        product.refresh_from_db()

        assert dn.status == DeliveryNoteStatus.DISPATCHED
        assert product.on_hand_qty == Decimal("5.00")  # 10 - 5 = 5
        assert product.reserved_qty == Decimal("0.00") # 5 - 5 = 0

        # Deliver Delivery Note
        delivery_services.deliver_delivery_note(dn, user)
        dn.refresh_from_db()
        so_line.refresh_from_db()
        order.refresh_from_db()

        assert dn.status == DeliveryNoteStatus.DELIVERED
        assert so_line.delivered_qty == Decimal("5.00")
        assert order.status == SalesOrderStatus.FULLY_DELIVERED


@pytest.mark.django_db
class TestDeliveryUIEndpoints:
    def test_endpoints(self, client, delivery_setup):
        product = delivery_setup["product"]
        user = delivery_setup["user"]

        client.force_login(user)

        # Receive 10 units in stock
        inventory_services.receive_stock(product, Decimal("10.00"), reference="Receipt")

        # Create confirmed sales order
        lines_data = [{"product": product, "quantity": Decimal("5.00"), "unit_price": Decimal("150.00")}]
        order = sales_services.create_order("Acme Corp", user, lines_data)
        sales_services.confirm_order(order)

        # 1. Post to create delivery note
        url_create = reverse("delivery:create", args=[order.pk])
        response = client.post(url_create)
        assert response.status_code == status.HTTP_302_FOUND
        
        dn = DeliveryNote.objects.filter(sales_order=order).first()
        assert dn is not None
        assert dn.status == DeliveryNoteStatus.PENDING

        # 2. Get list view
        url_list = reverse("delivery:list")
        response = client.get(url_list)
        assert response.status_code == status.HTTP_200_OK
        assert dn.delivery_number in response.content.decode()

        # 3. Get detail view
        url_detail = reverse("delivery:detail", args=[dn.pk])
        response = client.get(url_detail)
        assert response.status_code == status.HTTP_200_OK

        # 4. Dispatch via HTMX
        url_dispatch = reverse("delivery:dispatch", args=[dn.pk])
        response = client.post(url_dispatch, HTTP_HX_REQUEST="true")
        assert response.status_code == status.HTTP_200_OK
        dn.refresh_from_db()
        assert dn.status == DeliveryNoteStatus.DISPATCHED

        # 5. Deliver via HTMX
        url_deliver = reverse("delivery:deliver", args=[dn.pk])
        response = client.post(url_deliver, HTTP_HX_REQUEST="true")
        assert response.status_code == status.HTTP_200_OK
        dn.refresh_from_db()
        assert dn.status == DeliveryNoteStatus.DELIVERED
