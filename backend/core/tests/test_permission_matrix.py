"""
Role-based access regression matrix for the whole REST API (Phase 0.6).

The EXPECTED policy below is written out independently of apps.accounts.permissions
(MODULE_ACCESS / CAPABILITY_ROLES): if code and policy drift apart, these tests
fail. docs/architecture.md "Role and permission matrix" documents the same table.

For every endpoint and every role we check: allowed roles are not refused (any
status but 401/403), all other roles get 403. Anonymous, pending and suspended
users are refused everywhere, whatever their role.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import AccountStatus, UserRole as R

User = get_user_model()
ALL = list(R)

ADM, BO = R.ADMIN, R.BUSINESS_OWNER
SALES, PURCH, MFG, INV = R.SALES_USER, R.PURCHASE_USER, R.MANUFACTURING_USER, R.INVENTORY_MANAGER
ACC, TRADE, DOC, FIN, AUD = R.ACCOUNTANT, R.TRADE_MANAGER, R.DOCUMENTATION_OFFICER, R.FINANCE_MANAGER, R.AUDITOR

ORDER_READ = {ADM, BO, TRADE, DOC, FIN, AUD}
DOC_READ = {ADM, BO, TRADE, DOC, AUD}

# url name -> roles allowed to GET it
READ = {
    "api:user-list": {ADM, BO},
    "api:product-list": {ADM, BO, SALES, PURCH, INV},
    "api:category-list": {ADM, BO, SALES, PURCH, INV},
    "api:vendor-list": {ADM, BO, PURCH},
    "api:purchase-order-list": {ADM, BO, PURCH},
    "api:sales-order-list": {ADM, BO, SALES},
    "api:delivery-list": {ADM, BO, SALES, INV},
    "api:procurement-trigger-list": {ADM, BO, PURCH, INV},
    "api:work-center-list": {ADM, BO, MFG},
    "api:bom-list": {ADM, BO, MFG},
    "api:manufacturing-order-list": {ADM, BO, MFG},
    "api:work-order-list": {ADM, BO, MFG},
    "api:inventory-stock": {ADM, BO, MFG, INV},
    "api:inventory-stock-summary": {ADM, BO, MFG, INV},
    "api:inventory-ledger": {ADM, BO, MFG, INV},
    "api:export-order-list": ORDER_READ,
    "api:import-order-list": ORDER_READ,
    "api:trade-document-list": DOC_READ,
    "api:shipment-list": DOC_READ,
    "api:trade-customer-list": {ADM, BO, TRADE},
    "api:trade-supplier-list": {ADM, BO, TRADE},
    "api:country-list": ORDER_READ,
    "api:currency-list": ORDER_READ,
    "api:incoterm-list": ORDER_READ,
    "api:blockchain-document-list": {ADM, BO, TRADE, DOC, AUD},
    "api:blockchain-audit-log-list": {ADM, BO, TRADE, AUD},
    "api:report-overview": {ADM, BO, ACC},
    "api:audit-log-list": {ADM, BO, AUD},
    "api:dashboard-summary": {ADM, BO},
    # Role-filtered content, available to every approved user:
    "api:dashboard-overview": set(ALL),
    "api:dashboard-analytics": set(ALL),
    "api:dashboard-alerts": set(ALL),
    "api:auth-me": set(ALL),
}

# url name -> (roles allowed to POST, request format). Bodies are empty: an allowed
# role gets a validation error (400), a refused one 403.
WRITE = {
    "api:product-list": ({ADM, BO, INV, PURCH}, "json"),
    "api:category-list": ({ADM, BO, INV, PURCH}, "json"),
    "api:inventory-adjustments": ({ADM, BO, INV}, "json"),
    "api:sales-order-list": ({ADM, BO, SALES}, "json"),
    "api:purchase-order-list": ({ADM, BO, PURCH}, "json"),
    "api:vendor-list": ({ADM, BO, PURCH}, "json"),
    "api:delivery-list": ({ADM, BO, SALES, INV}, "json"),
    "api:work-center-list": ({ADM, BO, MFG}, "json"),
    "api:bom-list": ({ADM, BO, MFG}, "json"),
    "api:manufacturing-order-list": ({ADM, BO, MFG}, "json"),
    "api:export-order-list": ({ADM, BO, TRADE}, "json"),
    "api:import-order-list": ({ADM, BO, TRADE}, "json"),
    "api:trade-document-list": ({ADM, BO, TRADE, DOC}, "multipart"),
    "api:trade-customer-list": ({ADM, BO, TRADE}, "json"),
    "api:trade-supplier-list": ({ADM, BO, TRADE}, "json"),
}

REFUSED = (401, 403)


def _user(role, status=AccountStatus.APPROVED):
    return User.objects.create_user(
        email=f"{role.lower()}-{status.lower()}@matrix.test", password="x-Pass-12345",
        full_name=role, role=role, account_status=status,
    )


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_login(user)
    return client


def _mismatches(name, method, allowed, fmt="json"):
    out = []
    for role in ALL:
        response = getattr(_client(_user(role)), method)(reverse(name), {}, format=fmt) if method == "post" \
            else _client(_user(role)).get(reverse(name))
        refused = response.status_code in REFUSED
        if (role in allowed) == refused:
            out.append(f"{role}: got {response.status_code}, expected {'allowed' if role in allowed else 'refused'}")
        User.objects.filter(role=role).delete()
    return out


@pytest.mark.django_db
@pytest.mark.parametrize("name", sorted(READ))
def test_read_access_matrix(name):
    assert _mismatches(name, "get", READ[name]) == []


@pytest.mark.django_db
@pytest.mark.parametrize("name", sorted(WRITE))
def test_write_access_matrix(name):
    allowed, fmt = WRITE[name]
    assert _mismatches(name, "post", allowed, fmt) == []


@pytest.mark.django_db
@pytest.mark.parametrize("name", sorted(READ))
def test_anonymous_is_refused_everywhere(name):
    assert _client().get(reverse(name)).status_code in REFUSED


@pytest.mark.django_db
@pytest.mark.parametrize("status", [AccountStatus.PENDING, AccountStatus.REJECTED, AccountStatus.SUSPENDED])
def test_unapproved_admins_are_refused_everywhere(status):
    """Even with the ADMIN role, an unapproved account gets nothing (and loses its session)."""
    for name in sorted(READ):
        user = _user(ADM, status)
        response = _client(user).get(reverse(name))
        assert response.status_code == 403, (name, response.status_code)
        user.delete()
    for name, (_, fmt) in sorted(WRITE.items()):
        user = _user(ADM, status)
        assert _client(user).post(reverse(name), {}, format=fmt).status_code == 403, name
        user.delete()


@pytest.mark.django_db
def test_inactive_user_session_is_refused():
    user = _user(ADM)
    client = _client(user)
    User.objects.filter(pk=user.pk).update(is_active=False)
    assert client.get(reverse("api:product-list")).status_code in REFUSED


# --- CSV exports (HTML report downloads) ------------------------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize("report", ["reports:sales", "reports:purchase", "reports:manufacturing", "reports:inventory"])
def test_report_exports_restricted(report):
    for role in ALL:
        response = _client(_user(role)).get(reverse(report))
        allowed = role in {ADM, BO, ACC}
        assert (response.status_code == 200) == allowed, (report, role, response.status_code)
        if allowed:
            assert response["Content-Type"].startswith("text/csv")
        User.objects.filter(role=role).delete()


# --- dashboard data is filtered by role -----------------------------------------------------

@pytest.mark.django_db
def test_dashboard_analytics_only_returns_permitted_series():
    data = _client(_user(DOC)).get(reverse("api:dashboard-analytics")).json()
    assert set(data) == {"sales_trend", "purchase_trend", "manufacturing_progress", "inventory_movement"}
    assert all(series == [] for series in data.values())

    owner = _client(_user(BO)).get(reverse("api:dashboard-analytics")).json()
    assert set(owner) == set(data)


@pytest.mark.django_db
def test_dashboard_overview_hides_other_modules_activity():
    from apps.audit_logs.models import AuditLog, AuditLogAction

    import uuid

    actor = _user(ADM)
    AuditLog.objects.create(user=actor, module="sales", record_type="SalesOrder", record_id=uuid.uuid4(),
                            action=AuditLogAction.CREATED)
    AuditLog.objects.create(user=actor, module="foreign_trade", record_type="ExportOrder", record_id=uuid.uuid4(),
                            action=AuditLogAction.CREATED)

    doc_officer = _client(_user(DOC)).get(reverse("api:dashboard-overview")).json()
    assert {a["module"] for a in doc_officer["recent_activities"]} == {"foreign_trade"}

    sales = _client(_user(SALES)).get(reverse("api:dashboard-overview")).json()
    assert {a["module"] for a in sales["recent_activities"]} == {"sales"}
    assert all("module" not in i or i["module"] in {"sales", "products", "delivery", "dashboard"}
               for i in sales["intelligence_alerts"])


# --- voice assistant uses the same write rules ---------------------------------------------

@pytest.mark.django_db
def test_voice_actions_require_write_capability():
    from core.api_views import can_run_action

    sales = _user(SALES)
    assert can_run_action(sales, "lookup_product") is True
    assert can_run_action(sales, "create_product") is False      # reads products, can't create them
    assert can_run_action(_user(INV), "create_product") is True
    assert can_run_action(_user(MFG), "update_stock") is False      # sees stock, can't adjust it
    assert can_run_action(_user(ADM), "update_stock") is True
    assert can_run_action(_user(SALES, AccountStatus.PENDING), "lookup_product") is False
