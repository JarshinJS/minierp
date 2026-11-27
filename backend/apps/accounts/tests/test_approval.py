"""
Signup approval and account-status enforcement (Phase 0.6).

Before: OTP signup created an *active SALES_USER* with immediate ERP access, and a
Business Owner could promote anyone to ADMIN.
"""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts import services
from apps.accounts.models import AccountStatus, UserRole

User = get_user_model()
PASSWORD = "Str0ng-pass-phrase!"

pytestmark = pytest.mark.django_db


def make(role=UserRole.SALES_USER, status=AccountStatus.APPROVED, email=None, **extra):
    return User.objects.create_user(
        email=email or f"{role.lower()}-{status.lower()}@example.com", password=PASSWORD,
        full_name=f"{role} {status}", role=role, account_status=status, **extra,
    )


def api(user=None):
    client = APIClient()
    if user is not None:
        client.force_login(user)
    return client


def signup_via_otp(client, **extra_payload):
    """Run the real signup flow (start + verify) with a known OTP."""
    response = client.post(reverse("api:auth-signup"), {
        "email": "newbie@example.com", "full_name": "New Bie",
        "password": PASSWORD, "confirm_password": PASSWORD, **extra_payload,
    }, format="json")
    assert response.status_code == 202, response.content
    session = client.session
    session["signup_data"]["otp"] = "123456"
    session.save()
    response = client.post(reverse("api:auth-signup-verify"), {"otp": "123456", **extra_payload}, format="json")
    assert response.status_code == 201, response.content
    return User.objects.get(email="newbie@example.com"), response.json()


# --- signup -----------------------------------------------------------------------

def test_signup_creates_pending_account_without_access():
    client = APIClient()
    user, body = signup_via_otp(client)
    assert user.account_status == AccountStatus.PENDING
    assert body["account_status"] == "PENDING"
    assert not user.is_staff and not user.is_superuser

    # Correct password, but no session and a clear reason.
    response = client.post(reverse("api:auth-login"), {"email": user.email, "password": PASSWORD}, format="json")
    assert response.status_code == 403
    assert response.json()["code"] == "account_pending"
    assert client.get(reverse("api:auth-me")).status_code == 403
    assert client.get(reverse("api:sales-order-list")).status_code == 403


def test_signup_payload_cannot_escalate():
    client = APIClient()
    user, _ = signup_via_otp(
        client, role="ADMIN", account_status="APPROVED", is_staff=True, is_superuser=True, is_active=True,
    )
    assert user.account_status == AccountStatus.PENDING
    assert user.role != UserRole.ADMIN
    assert not user.is_staff and not user.is_superuser


def test_wrong_password_gives_generic_error_even_for_blocked_accounts():
    for status in (AccountStatus.PENDING, AccountStatus.SUSPENDED):
        user = make(status=status, email=f"{status}@x.com")
        response = APIClient().post(reverse("api:auth-login"), {"email": user.email, "password": "wrong-password"}, format="json")
        assert response.status_code == 400
        assert "code" not in response.json()


@pytest.mark.parametrize("status, code", [
    (AccountStatus.PENDING, "account_pending"),
    (AccountStatus.REJECTED, "account_rejected"),
    (AccountStatus.SUSPENDED, "account_suspended"),
])
def test_login_reports_status_only_with_correct_password(status, code):
    user = make(status=status)
    client = APIClient()
    response = client.post(reverse("api:auth-login"), {"email": user.email, "password": PASSWORD}, format="json")
    assert response.status_code == 403
    assert response.json()["code"] == code
    assert "_auth_user_id" not in client.session  # no session was created


def test_disabled_account_is_reported_after_password_check():
    user = make(is_active=False)
    response = APIClient().post(reverse("api:auth-login"), {"email": user.email, "password": PASSWORD}, format="json")
    assert response.status_code == 403
    assert response.json()["code"] == "account_disabled"


def test_approved_user_logs_in_normally():
    user = make()
    client = APIClient()
    response = client.post(reverse("api:auth-login"), {"email": user.email, "password": PASSWORD}, format="json")
    assert response.status_code == 200
    assert response.json()["account_status"] == "APPROVED"
    assert "capabilities" in response.json()
    assert client.get(reverse("api:sales-order-list")).status_code == 200


# --- existing sessions are cut off ------------------------------------------------------

def test_suspension_ends_existing_session_immediately():
    admin = make(UserRole.ADMIN, email="admin@x.com")
    victim = make(UserRole.SALES_USER, email="sales@x.com")
    client = api(victim)
    assert client.get(reverse("api:sales-order-list")).status_code == 200

    services.suspend_user(victim, actor=admin, note="investigation")

    response = client.get(reverse("api:sales-order-list"))
    assert response.status_code == 403 and response.json()["code"] == "account_suspended"
    assert "_auth_user_id" not in client.session
    # The session is gone, so even a later reinstatement needs a fresh login.
    assert client.get(reverse("api:auth-me")).status_code == 403


def test_blocked_session_is_refused_on_html_and_admin_pages():
    user = make(UserRole.ADMIN, status=AccountStatus.PENDING, email="pa@x.com", is_staff=True)
    client = api(user)
    assert client.get(reverse("accounts:user_list")).status_code == 403
    client = api(user)
    assert client.get("/admin/").status_code == 403


# --- approval rules -------------------------------------------------------------------

def test_admin_approves_with_explicit_role():
    admin = make(UserRole.ADMIN, email="admin@x.com")
    pending = make(status=AccountStatus.PENDING, email="p@x.com")
    url = reverse("api:user-approve", args=[pending.pk])

    assert api(admin).post(url, {}, format="json").status_code == 400  # role is required
    response = api(admin).post(url, {"role": "INVENTORY_MANAGER"}, format="json")
    assert response.status_code == 200, response.content
    pending.refresh_from_db()
    assert pending.account_status == AccountStatus.APPROVED
    assert pending.role == UserRole.INVENTORY_MANAGER
    assert pending.status_changed_by == admin and pending.status_changed_at


def test_business_owner_can_approve_regular_roles_only():
    owner = make(UserRole.BUSINESS_OWNER, email="bo@x.com")
    pending = make(status=AccountStatus.PENDING, email="p@x.com")
    url = reverse("api:user-approve", args=[pending.pk])

    for privileged in ("ADMIN", "BUSINESS_OWNER"):
        assert api(owner).post(url, {"role": privileged}, format="json").status_code == 403
    pending.refresh_from_db()
    assert pending.account_status == AccountStatus.PENDING

    assert api(owner).post(url, {"role": "SALES_USER"}, format="json").status_code == 200


def test_business_owner_cannot_promote_or_manage_admins():
    owner = make(UserRole.BUSINESS_OWNER, email="bo@x.com")
    admin = make(UserRole.ADMIN, email="admin@x.com")
    make(UserRole.ADMIN, email="admin2@x.com")
    sales = make(UserRole.SALES_USER, email="s@x.com")
    client = api(owner)

    assert client.post(reverse("api:user-change-role", args=[sales.pk]), {"role": "ADMIN"}, format="json").status_code == 403
    assert client.post(reverse("api:user-deactivate", args=[admin.pk])).status_code == 403
    assert client.post(reverse("api:user-suspend", args=[admin.pk]), {}, format="json").status_code == 403
    sales.refresh_from_db(); admin.refresh_from_db()
    assert sales.role == UserRole.SALES_USER and admin.is_active and admin.account_status == AccountStatus.APPROVED


def test_no_self_management():
    admin = make(UserRole.ADMIN, email="admin@x.com")
    for name, body in (("user-approve", {"role": "ADMIN"}), ("user-suspend", {}), ("user-reject", {}),
                       ("user-change-role", {"role": "SALES_USER"}), ("user-deactivate", None)):
        response = api(admin).post(reverse(f"api:{name}", args=[admin.pk]), body, format="json")
        assert response.status_code in (400, 403), name


def test_pending_user_cannot_approve_anyone_even_with_admin_role():
    sneaky = make(UserRole.ADMIN, status=AccountStatus.PENDING, email="sneaky@x.com")
    other = make(status=AccountStatus.PENDING, email="other@x.com")
    response = api(sneaky).post(reverse("api:user-approve", args=[other.pk]), {"role": "ADMIN"}, format="json")
    assert response.status_code == 403
    other.refresh_from_db()
    assert other.account_status == AccountStatus.PENDING


def test_non_managers_cannot_use_approval_endpoints():
    pending = make(status=AccountStatus.PENDING, email="p@x.com")
    for role in (UserRole.SALES_USER, UserRole.AUDITOR, UserRole.ACCOUNTANT, UserRole.TRADE_MANAGER):
        user = make(role, email=f"{role}@x.com")
        response = api(user).post(reverse("api:user-approve", args=[pending.pk]), {"role": "SALES_USER"}, format="json")
        assert response.status_code == 403, role


def test_status_transitions():
    admin = make(UserRole.ADMIN, email="admin@x.com")
    user = make(status=AccountStatus.PENDING, email="u@x.com")
    client = api(admin)

    assert client.post(reverse("api:user-suspend", args=[user.pk]), {}, format="json").status_code == 400
    assert client.post(reverse("api:user-reject", args=[user.pk]), {"note": "unknown person"}, format="json").status_code == 200
    user.refresh_from_db()
    assert user.account_status == AccountStatus.REJECTED and user.status_note == "unknown person"

    assert client.post(reverse("api:user-approve", args=[user.pk]), {"role": "SALES_USER"}, format="json").status_code == 200
    assert client.post(reverse("api:user-suspend", args=[user.pk]), {"note": "x"}, format="json").status_code == 200
    assert client.post(reverse("api:user-reinstate", args=[user.pk])).status_code == 200
    user.refresh_from_db()
    assert user.account_status == AccountStatus.APPROVED


def test_suspended_admin_can_no_longer_manage_accounts():
    from django.core.exceptions import PermissionDenied

    admin = make(UserRole.ADMIN, email="admin@x.com")
    other_admin = make(UserRole.ADMIN, email="admin2@x.com")
    services.suspend_user(other_admin, actor=admin)
    other_admin.refresh_from_db()
    with pytest.raises(PermissionDenied):
        services.suspend_user(admin, actor=other_admin)
    admin.refresh_from_db()
    assert admin.account_status == AccountStatus.APPROVED


def test_user_list_filters_pending():
    admin = make(UserRole.ADMIN, email="admin@x.com")
    make(status=AccountStatus.PENDING, email="p@x.com")
    rows = api(admin).get(reverse("api:user-list"), {"account_status": "PENDING"}).json()["results"]
    assert [r["email"] for r in rows] == ["p@x.com"]


def test_html_user_page_approve_and_reject():
    admin = make(UserRole.ADMIN, email="admin@x.com")
    pending = make(status=AccountStatus.PENDING, email="p@x.com")
    rejected_one = make(status=AccountStatus.PENDING, email="r@x.com")
    client = api(admin)

    page = client.get(reverse("accounts:user_list")).content.decode()
    assert "waiting for approval" in page and "Pending approval" in page

    url = reverse("accounts:user_status_action", args=[pending.pk, "approve"])
    assert client.post(url, {"role": "PURCHASE_USER"}).status_code == 200
    assert client.post(reverse("accounts:user_status_action", args=[rejected_one.pk, "reject"])).status_code == 200
    assert client.post(reverse("accounts:user_status_action", args=[pending.pk, "explode"])).status_code == 400
    pending.refresh_from_db(); rejected_one.refresh_from_db()
    assert pending.account_status == AccountStatus.APPROVED and pending.role == UserRole.PURCHASE_USER
    assert rejected_one.account_status == AccountStatus.REJECTED


def test_html_business_owner_cannot_grant_admin():
    owner = make(UserRole.BUSINESS_OWNER, email="bo@x.com")
    pending = make(status=AccountStatus.PENDING, email="p@x.com")
    client = api(owner)
    page = client.get(reverse("accounts:user_list")).content.decode()
    assert 'value="ADMIN"' not in page  # not even offered
    response = client.post(reverse("accounts:user_status_action", args=[pending.pk, "approve"]), {"role": "ADMIN"})
    assert response.status_code == 403
    sales = make(UserRole.SALES_USER, email="s@x.com")
    assert client.post(reverse("accounts:change_role", args=[sales.pk]), {"role": "ADMIN"}).status_code == 403


def test_demoted_admin_loses_staff_flag():
    admin = make(UserRole.ADMIN, email="admin@x.com")
    other = make(UserRole.ADMIN, email="admin2@x.com", is_staff=True)
    services.change_role(other, UserRole.SALES_USER, actor=admin)
    other.refresh_from_db()
    assert other.is_staff is False


def test_create_superuser_is_approved():
    su = User.objects.create_superuser(email="root@x.com", password=PASSWORD, full_name="Root")
    assert su.account_status == AccountStatus.APPROVED and su.is_approved


def test_model_default_is_pending():
    user = User.objects.create(email="raw@x.com", full_name="Raw")
    assert user.account_status == AccountStatus.PENDING and not user.is_approved


# --- migration: existing accounts keep working ----------------------------------------

@pytest.mark.django_db(transaction=True)
def test_migration_approves_existing_accounts_and_defaults_new_ones_to_pending():
    executor = MigrationExecutor(connection)
    executor.migrate([("accounts", "0003_alter_user_role")])
    old_apps = executor.loader.project_state([("accounts", "0003_alter_user_role")]).apps
    OldUser = old_apps.get_model("accounts", "User")
    OldUser.objects.create(email="legacy@x.com", full_name="Legacy", role="ADMIN",
                           password=make_password(PASSWORD), is_active=True, is_staff=True)

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())

    legacy = User.objects.get(email="legacy@x.com")
    assert legacy.account_status == AccountStatus.APPROVED
    assert APIClient().post(reverse("api:auth-login"), {"email": "legacy@x.com", "password": PASSWORD},
                            format="json").status_code == 200
    assert User.objects.create(email="new@x.com", full_name="New").account_status == AccountStatus.PENDING


# --- brute-force protection ----------------------------------------------------------------

def test_login_is_throttled_per_account_across_ips(monkeypatch):
    from rest_framework.throttling import SimpleRateThrottle

    # Generous per-IP limit, strict per-account limit; monkeypatch restores both afterwards.
    monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES",
                        {**SimpleRateThrottle.THROTTLE_RATES, "auth": "1000/min", "auth_account": "3/hour"})
    user = make(email="target@x.com")
    statuses = [
        APIClient(REMOTE_ADDR=f"10.0.0.{i}").post(reverse("api:auth-login"),
                                                   {"email": user.email, "password": "wrong"}, format="json").status_code
        for i in range(5)
    ]
    assert statuses[:3] == [400, 400, 400]
    assert statuses[3:] == [429, 429]
    # Another account is unaffected.
    other = make(email="other@x.com")
    assert APIClient().post(reverse("api:auth-login"), {"email": other.email, "password": PASSWORD},
                            format="json").status_code == 200
