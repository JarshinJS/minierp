import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from core.exceptions import DomainError, WorkflowError
from apps.products.models import Product, Category, UnitOfMeasure
from apps.inventory.models import InventoryLedgerEntry, LedgerEntryType
from apps.inventory import services as inventory_services
from apps.procurement.models import ProcurementRequest, ProcurementStatus
from apps.sales.models import SalesOrder, SalesOrderLine, SalesOrderStatus
from apps.sales import services

User = get_user_model()

@pytest.fixture
def sales_setup(db):
    category = Category.objects.create(name="Furniture")
    
    # Create product with 0 stock initially
    product = Product.objects.create(
        name="Oak Table",
        sku="OAK-TBL-01",
        category=category,
        cost_price=Decimal("50.00"),
        selling_price=Decimal("150.00"),
        unit_of_measure=UnitOfMeasure.PCS
    )
    
    user = User.objects.create_user(
        email="salesman@example.com",
        password="password",
        full_name="Sales Guy",
        role="SALES_USER"
    )
    
    return {
        "product": product,
        "user": user,
        "category": category
    }


@pytest.mark.django_db
class TestSalesWorkflow:
    def test_full_sales_workflow_no_shortage(self, sales_setup):
        product = sales_setup["product"]
        user = sales_setup["user"]

        # 1. Receive stock first so there is no shortage: add 10 units on hand
        inventory_services.receive_stock(product, Decimal("10.00"), reference="Initial Receipt")
        assert product.on_hand_qty == Decimal("10.00")
        assert product.reserved_qty == Decimal("0.00")

        # 2. Create sales order in DRAFT
        lines_data = [
            {"product": product, "quantity": Decimal("4.00"), "unit_price": Decimal("150.00")}
        ]
        order = services.create_order(
            customer_name="Acme Corp",
            created_by=user,
            lines_data=lines_data,
            notes="Handle with care"
        )
        assert order.status == SalesOrderStatus.DRAFT
        assert order.lines.count() == 1
        line = order.lines.first()
        assert line.quantity == Decimal("4.00")
        assert line.delivered_qty == Decimal("0.00")

        # 3. Confirm order (Reserves 4 units, no shortage)
        services.confirm_order(order)
        order.refresh_from_db()
        product.refresh_from_db()
        
        assert order.status == SalesOrderStatus.CONFIRMED
        assert product.reserved_qty == Decimal("4.00")
        assert product.on_hand_qty == Decimal("10.00")
        # No procurement request should be generated since we had 10 on hand
        assert ProcurementRequest.objects.filter(reference=order.order_number).exists() is False

        # 4. Deliver partial order (Deliver 2 of 4 units)
        deliveries = {line.id: Decimal("2.00")}
        services.deliver_order(order, deliveries)
        order.refresh_from_db()
        line.refresh_from_db()
        product.refresh_from_db()

        assert order.status == SalesOrderStatus.PARTIALLY_DELIVERED
        assert line.delivered_qty == Decimal("2.00")
        assert product.on_hand_qty == Decimal("8.00")      # 10 - 2 = 8
        assert product.reserved_qty == Decimal("2.00")     # 4 - 2 = 2
        
        # Verify inventory issue ledger entry exists
        ledger_entry = InventoryLedgerEntry.objects.filter(
            product=product,
            entry_type=LedgerEntryType.ISSUE,
            reference=order.order_number
        ).first()
        assert ledger_entry is not None
        assert ledger_entry.quantity == Decimal("2.00")

        # 5. Deliver remaining order (Full shipment)
        services.deliver_order(order)
        order.refresh_from_db()
        line.refresh_from_db()
        product.refresh_from_db()

        assert order.status == SalesOrderStatus.FULLY_DELIVERED
        assert line.delivered_qty == Decimal("4.00")
        assert product.on_hand_qty == Decimal("6.00")      # 8 - 2 = 6
        assert product.reserved_qty == Decimal("0.00")     # 2 - 2 = 0

    def test_sales_workflow_with_shortage(self, sales_setup):
        product = sales_setup["product"]
        user = sales_setup["user"]

        # Product starts with 0.00 stock. Order 5 units -> Shortage of 5.00 units
        lines_data = [
            {"product": product, "quantity": Decimal("5.00"), "unit_price": Decimal("150.00")}
        ]
        order = services.create_order(
            customer_name="Shortage Inc",
            created_by=user,
            lines_data=lines_data
        )

        services.confirm_order(order)
        order.refresh_from_db()
        product.refresh_from_db()

        assert order.status == SalesOrderStatus.CONFIRMED
        assert product.reserved_qty == Decimal("5.00")
        
        # Procurement request must be triggered since 0 < 5
        proc_req = ProcurementRequest.objects.filter(reference=order.order_number).first()
        assert proc_req is not None
        assert proc_req.product == product
        assert proc_req.quantity_needed == Decimal("5.00")
        assert proc_req.status == ProcurementStatus.PENDING

    def test_cancel_order_releases_reservations(self, sales_setup):
        product = sales_setup["product"]
        user = sales_setup["user"]

        # Reserve first
        lines_data = [
            {"product": product, "quantity": Decimal("3.00"), "unit_price": Decimal("150.00")}
        ]
        order = services.create_order(customer_name="Cancel Corp", created_by=user, lines_data=lines_data)
        services.confirm_order(order)
        product.refresh_from_db()
        assert product.reserved_qty == Decimal("3.00")

        # Cancel order
        services.cancel_order(order)
        order.refresh_from_db()
        product.refresh_from_db()

        assert order.status == SalesOrderStatus.CANCELLED
        # Reservation should be released back to 0
        assert product.reserved_qty == Decimal("0.00")


@pytest.mark.django_db
class TestSalesAPI:
    def test_drf_sales_endpoints(self, sales_setup):
        product = sales_setup["product"]
        user = User.objects.create_user(email="sales_api@example.com", password="password", role="ADMIN")
        
        client = APIClient()
        client.force_authenticate(user=user)

        # 1. Create SO via API
        url = reverse("sales:api_sales_order-list")
        data = {
            "customer_name": "Test Client",
            "notes": "Fast shipping",
            "lines": [
                {
                    "product": str(product.id),
                    "quantity": "10.00",
                    "unit_price": "140.00"
                }
            ]
        }
        response = client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        order_id = response.data["id"]
        
        order = SalesOrder.objects.get(pk=order_id)
        assert order.customer_name == "Test Client"
        assert order.status == SalesOrderStatus.DRAFT

        # 2. Confirm SO via custom API action
        confirm_url = reverse("sales:api_sales_order-confirm", args=[order_id])
        response = client.post(confirm_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == SalesOrderStatus.CONFIRMED

        # 3. Deliver SO via custom API action (Fails due to shortage since on_hand_qty is 0)
        deliver_url = reverse("sales:api_sales_order-deliver", args=[order_id])
        response = client.post(deliver_url, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Cannot issue" in response.data["detail"]

        # Cancel SO
        cancel_url = reverse("sales:api_sales_order-cancel", args=[order_id])
        response = client.post(cancel_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == SalesOrderStatus.CANCELLED


@pytest.mark.django_db
class TestSalesWorkflowExtraAndValidations:
    def test_sales_order_creation_validations(self, sales_setup):
        product = sales_setup["product"]
        user = sales_setup["user"]

        # 1. Empty customer
        with pytest.raises(DomainError) as exc:
            services.create_order(customer_name="", created_by=user, lines_data=[{"product": product, "quantity": 1, "unit_price": 10}])
        assert "Customer name is required" in str(exc.value)

        # 2. Empty lines
        with pytest.raises(DomainError) as exc:
            services.create_order(customer_name="Acme", created_by=user, lines_data=[])
        assert "must have at least one line item" in str(exc.value)

        # 3. Negative quantity
        with pytest.raises(DomainError) as exc:
            services.create_order(customer_name="Acme", created_by=user, lines_data=[{"product": product, "quantity": -5, "unit_price": 10}])
        assert "Quantity must be positive" in str(exc.value)

        # 4. Negative unit price
        with pytest.raises(DomainError) as exc:
            services.create_order(customer_name="Acme", created_by=user, lines_data=[{"product": product, "quantity": 5, "unit_price": -10}])
        assert "Unit price cannot be negative" in str(exc.value)

    def test_invalid_workflow_transitions(self, sales_setup):
        product = sales_setup["product"]
        user = sales_setup["user"]

        # Create draft order
        order = services.create_order(customer_name="Acme", created_by=user, lines_data=[{"product": product, "quantity": 5, "unit_price": 10}])

        # Deliver a DRAFT order (must fail)
        with pytest.raises(WorkflowError) as exc:
            services.deliver_order(order)
        assert "Only CONFIRMED or PARTIALLY_DELIVERED" in str(exc.value)

        # Confirm DRAFT -> cancels it -> confirm again (must fail)
        services.confirm_order(order)
        services.cancel_order(order)
        with pytest.raises(WorkflowError) as exc:
            services.confirm_order(order)
        assert "Only DRAFT sales orders" in str(exc.value)

        # Deliver a CANCELLED order (must fail)
        with pytest.raises(WorkflowError) as exc:
            services.deliver_order(order)
        assert "Only CONFIRMED or PARTIALLY_DELIVERED" in str(exc.value)

    def test_deliver_order_edge_cases(self, sales_setup):
        product = sales_setup["product"]
        user = sales_setup["user"]

        # Setup stock
        inventory_services.receive_stock(product, Decimal("10.00"), reference="Receipt")

        order = services.create_order(customer_name="Acme", created_by=user, lines_data=[{"product": product, "quantity": 5, "unit_price": 10}])
        services.confirm_order(order)

        line = order.lines.first()

        # 1. Deliver with empty dict (must fail)
        with pytest.raises(DomainError) as exc:
            services.deliver_order(order, {})
        assert "No valid quantities were specified" in str(exc.value)

        # 2. Over-deliver (deliver 10 when only 5 ordered - must fail)
        with pytest.raises(DomainError) as exc:
            services.deliver_order(order, {line.id: Decimal("10.00")})
        assert "Cannot deliver" in str(exc.value)

    def test_sales_audit_logs_generation(self, sales_setup):
        from apps.audit_logs.models import AuditLog, AuditLogAction
        product = sales_setup["product"]
        user = sales_setup["user"]

        # Setup stock
        inventory_services.receive_stock(product, Decimal("10.00"), reference="Receipt")

        order = services.create_order(customer_name="Acme", created_by=user, lines_data=[{"product": product, "quantity": 5, "unit_price": 10}])

        # Confirm
        services.confirm_order(order)
        confirm_log = AuditLog.objects.filter(record_id=order.id, action=AuditLogAction.STATUS_CHANGED, new_value=SalesOrderStatus.CONFIRMED).first()
        assert confirm_log is not None

        # Deliver
        services.deliver_order(order)
        deliver_log = AuditLog.objects.filter(record_id=order.id, action=AuditLogAction.STATUS_CHANGED, new_value=SalesOrderStatus.FULLY_DELIVERED).first()
        assert deliver_log is not None

