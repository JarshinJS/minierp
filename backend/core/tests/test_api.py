"""
End-to-end tests for the consolidated /api/ surface: auth, users, inventory,
delivery, procurement, reports, dashboard, foreign trade and the schema.
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import UserRole
from apps.foreign_trade.models import Country, Currency, ExportOrder, TradeCustomer, TradeSupplier
from apps.inventory import services as inventory_services
from apps.manufacturing import services as manufacturing_services
from apps.procurement.models import ProcurementTrigger
from apps.products.models import Category, Product
from apps.sales import services as sales_services

User = get_user_model()
PASSWORD = "Str0ng-pass-123"


def make_user(role, email=None):
    return User.objects.create_user(
        email=email or f"{role.lower()}@example.com", password=PASSWORD,
        full_name=role.replace("_", " ").title(), role=role,
    )


def client_for(user=None):
    client = APIClient()
    if user:
        client.force_login(user)
    return client


@pytest.fixture
def product(db):
    category = Category.objects.create(name="Furniture")
    p = Product.objects.create(
        name="Oak Table", sku="OAK-T", category=category,
        cost_price=Decimal("100.00"), selling_price=Decimal("250.00"), is_active=True,
    )
    inventory_services.receive_stock(p, Decimal("10"), "Opening stock")
    p.refresh_from_db()
    return p


# --- Auth ---------------------------------------------------------------------

@pytest.mark.django_db
class TestAuthAPI:
    def test_csrf_endpoint_sets_cookie(self):
        response = APIClient().get(reverse("api:auth-csrf"))
        assert response.status_code == 200
        assert "csrftoken" in response.cookies
        assert response.json()["csrfToken"]

    def test_login_requires_csrf_token(self):
        make_user(UserRole.SALES_USER)
        client = APIClient(enforce_csrf_checks=True)
        body = {"email": "sales_user@example.com", "password": PASSWORD}
        assert client.post(reverse("api:auth-login"), body, format="json").status_code == 403

        token = client.get(reverse("api:auth-csrf")).json()["csrfToken"]
        response = client.post(reverse("api:auth-login"), body, format="json", HTTP_X_CSRFTOKEN=token)
        assert response.status_code == 200
        assert response.json()["email"] == "sales_user@example.com"

    def test_login_logout_and_me(self):
        make_user(UserRole.SALES_USER)
        client = APIClient()
        assert client.get(reverse("api:auth-me")).status_code == 403
        response = client.post(reverse("api:auth-login"),
                               {"email": "sales_user@example.com", "password": PASSWORD}, format="json")
        assert response.status_code == 200
        me = client.get(reverse("api:auth-me")).json()
        assert me["role"] == UserRole.SALES_USER
        assert set(me["modules"]) == {"dashboard", "sales", "products", "delivery"}
        assert client.post(reverse("api:auth-logout")).status_code == 204
        assert client.get(reverse("api:auth-me")).status_code == 403

    def test_bad_credentials_rejected(self):
        make_user(UserRole.SALES_USER)
        response = APIClient().post(reverse("api:auth-login"),
                                    {"email": "sales_user@example.com", "password": "wrong"}, format="json")
        assert response.status_code == 400
        assert response.json()["detail"] == "Invalid email or password."

    def test_me_modules_follow_sidebar_restrictions(self):
        # Trade managers have "reports" in the module map, but the Reports page is
        # restricted to Admin/Owner/Accountant, so it must not be advertised.
        me = client_for(make_user(UserRole.TRADE_MANAGER)).get(reverse("api:auth-me")).json()
        assert "reports" not in me["modules"]
        assert "foreign_trade" in me["modules"]

    def test_login_is_rate_limited(self):
        client = APIClient()
        body = {"email": "nobody@example.com", "password": "x"}
        codes = [client.post(reverse("api:auth-login"), body, format="json").status_code for _ in range(11)]
        assert codes[:10] == [400] * 10
        assert codes[10] == 429

    def test_signup_flow(self):
        client = APIClient()
        response = client.post(reverse("api:auth-signup"), {
            "email": "new@example.com", "full_name": "New Person", "role": "ADMIN",
            "password": PASSWORD, "confirm_password": PASSWORD,
        }, format="json")
        assert response.status_code == 202
        otp = client.session["signup_data"]["otp"]
        assert otp in mail.outbox[0].body

        # Resend is on cooldown right after signup.
        resend = client.post(reverse("api:auth-signup-resend"))
        assert resend.status_code == 400 and resend.json()["restart"] is False

        response = client.post(reverse("api:auth-signup-verify"), {"otp": otp}, format="json")
        assert response.status_code == 201
        assert response.json()["role"] == UserRole.SALES_USER  # requested ADMIN is ignored

    def test_signup_validation_errors(self):
        response = APIClient().post(reverse("api:auth-signup"), {
            "email": "new@example.com", "full_name": "X", "password": "123", "confirm_password": "456",
        }, format="json")
        assert response.status_code == 400
        assert "non_field_errors" in response.json() or "password" in response.json()


# --- Users --------------------------------------------------------------------

@pytest.mark.django_db
class TestUsersAPI:
    def test_admin_manages_users(self):
        admin = make_user(UserRole.ADMIN)
        target = make_user(UserRole.SALES_USER)
        client = client_for(admin)

        listing = client.get(reverse("api:user-list"), {"role": "SALES_USER"}).json()
        assert [u["email"] for u in listing["results"]] == [target.email]

        url = reverse("api:user-change-role", args=[target.pk])
        assert client.post(url, {"role": "PURCHASE_USER"}, format="json").json()["role"] == "PURCHASE_USER"
        assert client.post(reverse("api:user-deactivate", args=[target.pk])).json()["is_active"] is False
        assert client.post(reverse("api:user-activate", args=[target.pk])).json()["is_active"] is True
        assert len(client.get(reverse("api:user-roles")).json()) == len(UserRole.choices)

    def test_cannot_change_own_account(self):
        admin = make_user(UserRole.ADMIN)
        response = client_for(admin).post(reverse("api:user-deactivate", args=[admin.pk]))
        assert response.status_code == 400

    def test_non_admin_forbidden(self):
        user = make_user(UserRole.SALES_USER)
        assert client_for(user).get(reverse("api:user-list")).status_code == 403


# --- Inventory ----------------------------------------------------------------

@pytest.mark.django_db
class TestInventoryAPI:
    def test_stock_summary_ledger_and_adjustments(self, product):
        client = client_for(make_user(UserRole.INVENTORY_MANAGER))

        stock = client.get(reverse("api:inventory-stock"), {"search": "oak"}).json()
        assert stock["results"][0]["avail_qty"] == "10.00"

        summary = client.get(reverse("api:inventory-stock-summary")).json()
        assert summary["total_skus"] == 1 and summary["total_value"] == "1000.00"

        response = client.post(reverse("api:inventory-adjustments"), {
            "product": str(product.pk), "adjustment_type": "ISSUE", "quantity": "4",
        }, format="json")
        assert response.status_code == 201
        assert response.json()["on_hand_qty"] == "6.00"

        too_many = client.post(reverse("api:inventory-adjustments"), {
            "product": str(product.pk), "adjustment_type": "ISSUE", "quantity": "100",
        }, format="json")
        assert too_many.status_code == 400 and "Cannot issue" in too_many.json()["detail"]

        ledger = client.get(reverse("api:inventory-ledger"), {"entry_type": "ISSUE"}).json()
        assert ledger["count"] == 1

    def test_sales_user_has_no_inventory_access(self, product):
        client = client_for(make_user(UserRole.SALES_USER))
        assert client.get(reverse("api:inventory-stock")).status_code == 403


# --- Delivery -----------------------------------------------------------------

@pytest.mark.django_db
class TestDeliveryAPI:
    def _confirmed_order(self, product, user):
        order = sales_services.create_order(
            "Acme", user, [{"product": product, "quantity": Decimal("3"), "unit_price": Decimal("250")}],
        )
        sales_services.confirm_order(order)
        return order

    def test_create_dispatch_deliver(self, product):
        sales = make_user(UserRole.SALES_USER)
        inventory = make_user(UserRole.INVENTORY_MANAGER, email="inv@example.com")
        order = self._confirmed_order(product, sales)

        created = client_for(sales).post(reverse("api:delivery-list"), {"sales_order": str(order.pk)}, format="json")
        assert created.status_code == 201
        note = created.json()
        assert note["status"] == "PENDING" and note["lines"][0]["quantity"] == "3.00"

        # Sales users may not dispatch (warehouse action); inventory managers may.
        dispatch_url = reverse("api:delivery-dispatch-note", args=[note["id"]])
        assert client_for(sales).post(dispatch_url).status_code == 403
        assert client_for(inventory).post(dispatch_url).json()["status"] == "DISPATCHED"

        delivered = client_for(sales).post(reverse("api:delivery-deliver", args=[note["id"]]))
        assert delivered.json()["status"] == "DELIVERED"
        product.refresh_from_db()
        assert product.on_hand_qty == Decimal("7.00")

    def test_nothing_pending_is_rejected(self, product):
        sales = make_user(UserRole.SALES_USER)
        order = self._confirmed_order(product, sales)
        client = client_for(sales)
        client.post(reverse("api:delivery-list"), {"sales_order": str(order.pk)}, format="json")
        again = client.post(reverse("api:delivery-list"), {"sales_order": str(order.pk)}, format="json")
        assert again.status_code == 400


# --- Procurement --------------------------------------------------------------

@pytest.mark.django_db
def test_procurement_triggers(product):
    ProcurementTrigger.objects.create(product=product, quantity_needed=Decimal("5"), status="FAILED")
    client = client_for(make_user(UserRole.PURCHASE_USER))
    assert client.get(reverse("api:procurement-trigger-list"), {"status": "FAILED"}).json()["count"] == 1
    summary = client.get(reverse("api:procurement-trigger-summary")).json()
    assert summary["failed"] == 1 and summary["queued"] == 0


# --- Reports ------------------------------------------------------------------

@pytest.mark.django_db
class TestReportsAPI:
    def test_overview_json_and_csv(self, product):
        user = make_user(UserRole.ACCOUNTANT)
        order = sales_services.create_order(
            "Acme", user, [{"product": product, "quantity": Decimal("2"), "unit_price": Decimal("250")}],
        )
        cancelled = sales_services.create_order(
            "Acme", user, [{"product": product, "quantity": Decimal("9"), "unit_price": Decimal("250")}],
        )
        sales_services.cancel_order(cancelled)
        client = client_for(user)

        overview = client.get(reverse("api:report-overview")).json()
        assert overview["sales_total"] == 1
        assert "daily" in overview["available_reports"]["sales"]

        by_customer = client.get(reverse("api:report-detail", args=["sales", "customer"])).json()
        # Cancelled orders are excluded from both the count and the revenue.
        assert by_customer["rows"] == [["Acme", 1, "500.00"]]
        assert order.order_number  # sanity

        csv_response = client.get(reverse("api:report-detail", args=["sales", "customer"]), {"format": "csv"})
        assert csv_response["Content-Type"].startswith("text/csv")
        assert "attachment" in csv_response["Content-Disposition"]
        assert csv_response.content.decode().splitlines()[1] == "Acme,1,500.00"

    def test_consumption_report_with_bom_lines(self, product):
        component = Product.objects.create(name="Oak Plank", sku="PLANK", category=product.category,
                                           cost_price=Decimal("5"), selling_price=Decimal("8"), is_active=True)
        bom = manufacturing_services.create_bom(
            name="Table BOM", reference="BOM-T", product=product,
            components=[{"component_id": str(component.pk), "quantity": "4", "uom": "PCS", "sequence": 1}],
        )
        product.default_bom = bom
        product.save(update_fields=["default_bom"])
        report = client_for(make_user(UserRole.ACCOUNTANT)).get(
            reverse("api:report-detail", args=["manufacturing", "consumption"])).json()
        assert report["rows"] == [["Oak Table", "PLANK", "Oak Plank", "4.0000"]]

    def test_unknown_report_and_role(self):
        assert client_for(make_user(UserRole.ACCOUNTANT)).get(
            reverse("api:report-detail", args=["sales", "nope"])).status_code == 404
        assert client_for(make_user(UserRole.TRADE_MANAGER)).get(
            reverse("api:report-overview")).status_code == 403


# --- Dashboard ----------------------------------------------------------------

@pytest.mark.django_db
def test_dashboard_alerts(product):
    Product.objects.create(name="Rare Chair", sku="RARE", category=product.category,
                           cost_price=Decimal("1"), selling_price=Decimal("2"), is_active=True)
    data = client_for(make_user(UserRole.ACCOUNTANT)).get(reverse("api:dashboard-alerts")).json()
    low = next(item for item in data["items"] if item["key"] == "low_stock")
    assert low["count"] >= 1
    assert low["can_open"] is False  # accountants can't open Inventory
    assert "url_name" not in low


# --- Foreign trade --------------------------------------------------------------

@pytest.fixture
def trade_refs(db):
    country = Country.objects.create(name="Netherlands", code="NL")
    currency = Currency.objects.create(code="EUR", name="Euro", symbol="€", exchange_rate=Decimal("1"))
    customer = TradeCustomer.objects.create(name="Dutch Living", country=country)
    supplier = TradeSupplier.objects.create(name="Teak Co", country=country)
    return {"country": country, "currency": currency, "customer": customer, "supplier": supplier}


@pytest.mark.django_db
class TestForeignTradeAPI:
    def _create_export(self, client, refs):
        return client.post(reverse("api:export-order-list"), {
            "customer_id": str(refs["customer"].pk), "country_id": str(refs["country"].pk),
            "currency_id": str(refs["currency"].pk), "port_of_loading": "Mumbai",
            "lines_data": [{"description": "Oak tables", "quantity": "10", "unit_price": "300"}],
        }, format="json")

    def test_export_order_lifecycle(self, trade_refs):
        manager = client_for(make_user(UserRole.TRADE_MANAGER))
        created = self._create_export(manager, trade_refs)
        assert created.status_code == 201, created.json()
        order = created.json()
        assert order["status"] == "DRAFT" and order["total_amount"] == "3000.00"

        patched = manager.patch(reverse("api:export-order-detail", args=[order["id"]]),
                                {"port_of_destination": "Rotterdam"}, format="json")
        assert patched.json()["port_of_destination"] == "Rotterdam"

        assert manager.post(reverse("api:export-order-confirm", args=[order["id"]])).json()["status"] == "CONFIRMED"
        # No more edits once confirmed.
        assert manager.patch(reverse("api:export-order-detail", args=[order["id"]]),
                             {"notes": "x"}, format="json").status_code == 400

        shipped = manager.post(reverse("api:export-order-ship", args=[order["id"]]),
                               {"carrier": "Maersk"}, format="json").json()
        assert shipped["order"]["status"] == "SHIPPED" and shipped["shipment"]["carrier"] == "Maersk"
        assert manager.post(reverse("api:export-order-deliver", args=[order["id"]])).json()["status"] == "DELIVERED"

        # Finance can raise invoices but not drive the order workflow.
        finance = client_for(make_user(UserRole.FINANCE_MANAGER))
        invoice = finance.post(reverse("api:export-order-invoices", args=[order["id"]]), {}, format="json")
        assert invoice.status_code == 201 and invoice.json()["amount"] == "3000.00"
        assert len(finance.get(reverse("api:export-order-invoices", args=[order["id"]])).json()) == 1
        assert finance.post(reverse("api:export-order-cancel", args=[order["id"]])).status_code == 403

    def test_create_requires_lines(self, trade_refs):
        manager = client_for(make_user(UserRole.TRADE_MANAGER))
        response = manager.post(reverse("api:export-order-list"), {
            "customer_id": str(trade_refs["customer"].pk), "country_id": str(trade_refs["country"].pk),
            "currency_id": str(trade_refs["currency"].pk),
        }, format="json")
        assert response.status_code == 400

    def test_import_order_lifecycle(self, trade_refs):
        manager = client_for(make_user(UserRole.TRADE_MANAGER))
        order = manager.post(reverse("api:import-order-list"), {
            "supplier_id": str(trade_refs["supplier"].pk), "country_id": str(trade_refs["country"].pk),
            "currency_id": str(trade_refs["currency"].pk),
            "lines_data": [{"description": "Teak logs", "quantity": "5", "unit_price": "80"}],
        }, format="json").json()
        for step, expected in [("confirm", "CONFIRMED"), ("transit", "IN_TRANSIT"),
                               ("customs", "CUSTOMS"), ("receive", "RECEIVED")]:
            response = manager.post(reverse(f"api:import-order-{step}", args=[order["id"]]), {}, format="json")
            body = response.json()
            assert (body.get("order") or body)["status"] == expected, (step, body)

    def test_document_upload_and_verify(self, trade_refs, settings, tmp_path):
        settings.MEDIA_ROOT = tmp_path
        manager = client_for(make_user(UserRole.TRADE_MANAGER))
        order_id = self._create_export(manager, trade_refs).json()["id"]
        docs = client_for(make_user(UserRole.DOCUMENTATION_OFFICER))

        bad = docs.post(reverse("api:trade-document-list"), {
            "order_type": "export", "order_id": order_id, "document_type": "COMMERCIAL_INVOICE", "title": "Bad",
            "file": SimpleUploadedFile("evil.exe", b"MZ"),
        }, format="multipart")
        assert bad.status_code == 400 and "file" in bad.json()

        good = docs.post(reverse("api:trade-document-list"), {
            "order_type": "export", "order_id": order_id, "document_type": "COMMERCIAL_INVOICE", "title": "Invoice",
            "file": SimpleUploadedFile("invoice.pdf", b"%PDF-1.4 test", content_type="application/pdf"),
        }, format="multipart")
        assert good.status_code == 201, good.json()
        doc = good.json()
        assert doc["order_type"] == "export" and doc["version"] == 1

        listed = docs.get(reverse("api:trade-document-list"), {"order_type": "export", "order_id": order_id}).json()
        assert listed["count"] == 1
        auditor = client_for(make_user(UserRole.AUDITOR))
        assert "verified" in auditor.post(reverse("api:trade-document-verify", args=[doc["id"]])).json()

    def test_partners_and_reference_data(self, trade_refs):
        manager = client_for(make_user(UserRole.TRADE_MANAGER))
        created = manager.post(reverse("api:trade-customer-list"),
                               {"name": "Oslo Homes", "country_id": str(trade_refs["country"].pk)}, format="json")
        assert created.status_code == 201
        assert manager.get(reverse("api:trade-customer-list"), {"search": "oslo"}).json()["count"] == 1
        assert manager.get(reverse("api:country-list")).json()[0]["code"] == "NL"
        assert client_for(make_user(UserRole.AUDITOR)).get(reverse("api:trade-customer-list")).status_code == 403

    def test_html_workflow_views_enforce_roles(self, trade_refs):
        manager = make_user(UserRole.TRADE_MANAGER)
        order_id = self._create_export(client_for(manager), trade_refs).json()["id"]
        intruder = client_for(make_user(UserRole.SALES_USER))
        assert intruder.post(reverse("foreign_trade:export_order_cancel", args=[order_id])).status_code == 403
        assert ExportOrder.objects.get(pk=order_id).status == "DRAFT"


# --- Schema -------------------------------------------------------------------

@pytest.mark.django_db
def test_schema_requires_login():
    assert APIClient().get(reverse("api:schema")).status_code == 403
    response = client_for(make_user(UserRole.SALES_USER)).get(reverse("api:schema"))
    assert response.status_code == 200
    assert b"/api/inventory/adjustments/" in response.content


# --- Products API additions (used by the Next.js frontend) ---------------------

@pytest.mark.django_db
class TestProductsAPIForFrontend:
    def test_filters_display_fields_and_deactivate(self, product):
        client = client_for(make_user(UserRole.SALES_USER))
        listing = client.get(reverse("api:product-list"), {"search": "oak", "status": "active"}).json()
        assert listing["count"] == 1
        row = listing["results"][0]
        assert row["unit_of_measure_display"] == "Pieces" and row["category_name"] == "Furniture"
        assert client.get(reverse("api:product-list"), {"status": "inactive"}).json()["count"] == 0

        deactivated = client.post(reverse("api:product-deactivate", args=[product.pk])).json()
        assert deactivated["is_active"] is False
        assert client.get(reverse("api:product-list"), {"status": "inactive"}).json()["count"] == 1
        # Deactivating twice is a business-rule error, not a crash.
        assert client.post(reverse("api:product-deactivate", args=[product.pk])).status_code == 400


@pytest.mark.django_db
def test_dashboard_overview_is_role_filtered(product):
    admin = client_for(make_user(UserRole.ADMIN)).get(reverse("api:dashboard-overview")).json()
    assert {w["class_name"] for w in admin["widgets"]} >= {"ProductWidget", "SalesWidget"}
    assert "icon" not in admin["widgets"][0]

    accountant = client_for(make_user(UserRole.ACCOUNTANT)).get(reverse("api:dashboard-overview")).json()
    assert "SalesWidget" not in {w["class_name"] for w in accountant["widgets"]}
    assert accountant["low_stock"] == [] and accountant["pending_deliveries"] == []
