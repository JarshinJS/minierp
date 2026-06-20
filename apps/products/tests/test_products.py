import pytest
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from core.exceptions import DomainError
from apps.purchase.models import Vendor
from apps.manufacturing.models import BoM
from apps.products.models import Product, Category, UnitOfMeasure, ProcurementType
from apps.products import services
from apps.products import selectors

User = get_user_model()

@pytest.fixture
def product_setup(db):
    category = Category.objects.create(name="Chairs", description="All types of seating chairs")
    vendor = Vendor.objects.create(name="Wood Supplier Inc.", code="WS-001")
    bom = BoM.objects.create(name="Wooden Chair Recipe", code="BOM-WCH")
    
    return {
        "category": category,
        "vendor": vendor,
        "bom": bom
    }


@pytest.mark.django_db
class TestProductServices:
    def test_create_product_success(self, product_setup):
        product = services.create_product(
            name="Dining Chair",
            sku="WCH-01",
            category=product_setup["category"],
            cost_price="15.50",
            selling_price="45.00",
            unit_of_measure=UnitOfMeasure.PCS,
            procure_on_demand=True,
            procurement_type=ProcurementType.MANUFACTURING,
            default_vendor=product_setup["vendor"],
            default_bom=product_setup["bom"]
        )
        
        assert product.name == "Dining Chair"
        assert product.sku == "WCH-01"
        assert product.category == product_setup["category"]
        assert product.cost_price == Decimal("15.50")
        assert product.selling_price == Decimal("45.00")
        assert product.unit_of_measure == UnitOfMeasure.PCS
        assert product.procure_on_demand is True
        assert product.procurement_type == ProcurementType.MANUFACTURING
        assert product.default_vendor == product_setup["vendor"]
        assert product.default_bom == product_setup["bom"]
        # Quantities must always default to 0
        assert product.on_hand_qty == Decimal("0.0")
        assert product.reserved_qty == Decimal("0.0")
        assert product.available_qty == Decimal("0.0")

    def test_create_product_duplicate_sku(self, product_setup):
        services.create_product(
            name="Chair 1",
            sku="SKU-DUP",
            category=product_setup["category"],
            cost_price="10.00",
            selling_price="20.00",
            unit_of_measure=UnitOfMeasure.PCS
        )
        with pytest.raises(DomainError) as exc:
            services.create_product(
                name="Chair 2",
                sku="SKU-DUP",
                category=product_setup["category"],
                cost_price="12.00",
                selling_price="22.00",
                unit_of_measure=UnitOfMeasure.PCS
            )
        assert "already exists" in str(exc.value)

    def test_create_product_negative_prices(self, product_setup):
        with pytest.raises(DomainError):
            services.create_product(
                name="Bad Chair",
                sku="SKU-BAD",
                category=product_setup["category"],
                cost_price="-5.00",
                selling_price="20.00",
                unit_of_measure=UnitOfMeasure.PCS
            )

    def test_update_product_success(self, product_setup):
        product = services.create_product(
            name="Office Chair",
            sku="OFF-CH-01",
            category=product_setup["category"],
            cost_price="20.00",
            selling_price="50.00",
            unit_of_measure=UnitOfMeasure.PCS
        )
        
        updated = services.update_product(
            product,
            name="Updated Office Chair",
            cost_price="25.00",
            selling_price="55.00"
        )
        
        assert updated.name == "Updated Office Chair"
        assert updated.cost_price == Decimal("25.00")
        assert updated.selling_price == Decimal("55.00")

    def test_update_product_stock_readonly(self, product_setup):
        product = services.create_product(
            name="Office Chair",
            sku="OFF-CH-01",
            category=product_setup["category"],
            cost_price="20.00",
            selling_price="50.00",
            unit_of_measure=UnitOfMeasure.PCS
        )
        # Attempt to change stock levels through update_product service
        with pytest.raises(DomainError) as exc:
            services.update_product(product, on_hand_qty="100.00")
        assert "Cannot update stock quantity" in str(exc.value)

    def test_deactivate_product(self, product_setup):
        product = services.create_product(
            name="Foldable Table",
            sku="TBL-01",
            category=product_setup["category"],
            cost_price="30.00",
            selling_price="75.00",
            unit_of_measure=UnitOfMeasure.PCS
        )
        assert product.is_active is True
        services.deactivate_product(product)
        assert product.is_active is False


@pytest.mark.django_db
class TestProductSelectors:
    def test_get_products_filtering(self, product_setup):
        other_cat = Category.objects.create(name="Tables")
        p1 = services.create_product(
            name="Oak Chair", sku="OAK-CH", category=product_setup["category"], cost_price=10, selling_price=20, unit_of_measure="PCS"
        )
        p2 = services.create_product(
            name="Pine Table", sku="PINE-TB", category=other_cat, cost_price=15, selling_price=30, unit_of_measure="PCS"
        )
        
        # Search match
        search_res = list(selectors.get_products(search_query="Oak"))
        assert p1 in search_res
        assert p2 not in search_res

        # Category match
        cat_res = list(selectors.get_products(category_id=product_setup["category"].id))
        assert p1 in cat_res
        assert p2 not in cat_res

        # Invalid Category UUID match does not crash and returns empty list
        invalid_cat_res = list(selectors.get_products(category_id="invalid-uuid"))
        assert len(invalid_cat_res) == 0

    def test_get_product_stock_selector(self, product_setup):
        product = services.create_product(
            name="Oak Chair", sku="OAK-CH", category=product_setup["category"], cost_price=10, selling_price=20, unit_of_measure="PCS"
        )
        # Directly mock stock update (simulating inventory module update)
        product.on_hand_qty = Decimal("50.00")
        product.reserved_qty = Decimal("10.00")
        product.save()

        stock_info = selectors.get_product_stock(product)
        assert stock_info["on_hand"] == Decimal("50.00")
        assert stock_info["reserved"] == Decimal("10.00")
        assert stock_info["available"] == Decimal("40.00")


@pytest.mark.django_db
class TestProductAPI:
    def test_drf_endpoints_crud_and_stock(self, product_setup):
        # Create a user to authenticate API calls
        user = User.objects.create_user(email="api@example.com", password="password", role="ADMIN")
        client = APIClient()
        client.force_authenticate(user=user)

        # 1. Create product via API
        url = reverse("products:api_product-list")
        data = {
            "name": "Mahogany Chair",
            "sku": "MAH-CH",
            "category": str(product_setup["category"].id),
            "unit_of_measure": "PCS",
            "cost_price": "50.00",
            "selling_price": "120.00"
        }
        response = client.post(url, data)
        assert response.status_code == status.HTTP_201_CREATED
        
        product_id = response.data["id"]
        product = Product.objects.get(pk=product_id)
        assert product.name == "Mahogany Chair"
        # Verify read-only initial stock values
        assert product.on_hand_qty == Decimal("0.0")

        # 2. Update product cost via API
        detail_url = reverse("products:api_product-detail", args=[product_id])
        update_data = {
            "name": "Premium Mahogany Chair",
            "sku": "MAH-CH",
            "cost_price": "60.00",
            "selling_price": "130.00",
            "category": str(product_setup["category"].id),
            "unit_of_measure": "PCS"
        }
        response = client.put(detail_url, update_data)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Premium Mahogany Chair"
        assert response.data["cost_price"] == "60.00"

        # 3. Verify stock read-only via API
        bad_update_data = update_data.copy()
        bad_update_data["on_hand_qty"] = "500.00"
        response = client.put(detail_url, bad_update_data)
        # The serializer read_only_fields ignore on_hand_qty so it returns 200,
        # but the db values should remain unchanged (0.0)
        assert response.status_code == status.HTTP_200_OK
        product.refresh_from_db()
        assert product.on_hand_qty == Decimal("0.0")

        # 4. Custom stock endpoint
        stock_url = reverse("products:api_product-stock", args=[product_id])
        response = client.get(stock_url)
        assert response.status_code == status.HTTP_200_OK
        assert response.data["available"] == Decimal("0.00")


@pytest.mark.django_db
class TestProductExtraServices:
    def test_create_product_validations(self, product_setup):
        with pytest.raises(DomainError) as exc:
            services.create_product(name="", sku="TEST-SKU", category=product_setup["category"], cost_price=10, selling_price=20, unit_of_measure="PCS")
        assert "name cannot be empty" in str(exc.value)

        with pytest.raises(DomainError) as exc:
            services.create_product(name="Test", sku="", category=product_setup["category"], cost_price=10, selling_price=20, unit_of_measure="PCS")
        assert "SKU cannot be empty" in str(exc.value)

    def test_update_product_validations(self, product_setup):
        p1 = services.create_product(name="P1", sku="SKU-1", category=product_setup["category"], cost_price=10, selling_price=20, unit_of_measure="PCS")
        p2 = services.create_product(name="P2", sku="SKU-2", category=product_setup["category"], cost_price=10, selling_price=20, unit_of_measure="PCS")

        with pytest.raises(DomainError) as exc:
            services.update_product(p1, sku="")
        assert "SKU cannot be empty" in str(exc.value)

        with pytest.raises(DomainError) as exc:
            services.update_product(p1, sku="SKU-2")
        assert "already exists" in str(exc.value)

        with pytest.raises(DomainError) as exc:
            services.update_product(p1, cost_price=-5)
        assert "Cost price cannot be negative" in str(exc.value)

        with pytest.raises(DomainError) as exc:
            services.update_product(p1, selling_price=-5)
        assert "Selling price cannot be negative" in str(exc.value)

    def test_deactivate_already_inactive(self, product_setup):
        p = services.create_product(name="P", sku="SKU-P", category=product_setup["category"], cost_price=10, selling_price=20, unit_of_measure="PCS")
        services.deactivate_product(p)
        with pytest.raises(DomainError) as exc:
            services.deactivate_product(p)
        assert "already inactive" in str(exc.value)

    def test_audit_logs_for_product_events(self, product_setup):
        from apps.audit_logs.models import AuditLog, AuditLogAction
        
        # 1. Product creation audit log (created automatically via signal)
        p = services.create_product(name="Audit P", sku="AUDIT-P", category=product_setup["category"], cost_price=Decimal("10.00"), selling_price=Decimal("20.00"), unit_of_measure="PCS")
        creation_log = AuditLog.objects.filter(record_id=p.id, action=AuditLogAction.CREATED).first()
        assert creation_log is not None

        # 2. General update log (no price/status changed)
        services.update_product(p, name="Audit P Updated")
        update_log = AuditLog.objects.filter(record_id=p.id, action=AuditLogAction.UPDATED).first()
        assert update_log is not None

        # 3. Price change log
        services.update_product(p, cost_price=Decimal("15.00"), selling_price=Decimal("25.00"))
        cost_log = AuditLog.objects.filter(record_id=p.id, action=AuditLogAction.PRICE_CHANGED, field_changed="cost_price").first()
        selling_log = AuditLog.objects.filter(record_id=p.id, action=AuditLogAction.PRICE_CHANGED, field_changed="selling_price").first()
        assert cost_log is not None
        assert cost_log.old_value == "10.00"
        assert cost_log.new_value == "15.00"
        assert selling_log is not None
        assert selling_log.old_value == "20.00"
        assert selling_log.new_value == "25.00"

        # 4. Deactivation log
        services.deactivate_product(p)
        deact_log = AuditLog.objects.filter(record_id=p.id, action=AuditLogAction.STATUS_CHANGED, field_changed="is_active").first()
        assert deact_log is not None
        assert deact_log.old_value == "True"
        assert deact_log.new_value == "False"

