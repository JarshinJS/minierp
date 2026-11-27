"""
services.py for the Accounts app.

This module contains the services logic for the Accounts functionality.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from core.exceptions import DomainError, WorkflowError
from .models import AccountStatus, UserRole

User = get_user_model()

# Roles that may manage accounts at all, and the roles only an ADMIN may grant,
# revoke or act upon (otherwise a Business Owner could create admins).
ACCOUNT_MANAGER_ROLES = {UserRole.ADMIN, UserRole.BUSINESS_OWNER}
PRIVILEGED_ROLES = {UserRole.ADMIN, UserRole.BUSINESS_OWNER}


def check_can_manage(actor, target, new_role=None):
    """
    Raise PermissionDenied unless ``actor`` may manage ``target`` (and, if given,
    assign ``new_role``). Enforced in the service layer so every caller (REST API,
    HTML views, scripts passing an actor) gets the same rules:

    * the actor must be an approved Admin or Business Owner;
    * nobody can manage their own account (no self-approval / self-promotion);
    * only an Admin may act on Admin/Business Owner accounts or grant those roles.
    """
    if actor is None or not getattr(actor, "is_approved", False) or actor.role not in ACCOUNT_MANAGER_ROLES:
        raise PermissionDenied("You are not allowed to manage user accounts.")
    if actor.pk == target.pk:
        raise PermissionDenied("You cannot change your own account.")
    if actor.role != UserRole.ADMIN and (target.role in PRIVILEGED_ROLES or new_role in PRIVILEGED_ROLES):
        raise PermissionDenied("Only an Admin can manage Admin or Business Owner accounts.")


def _active_admin_count():
    return User.objects.filter(
        role=UserRole.ADMIN, is_active=True, account_status=AccountStatus.APPROVED,
    ).count()


def _set_status(user, status, actor, note=""):
    user.account_status = status
    user.status_changed_at = timezone.now()
    user.status_changed_by = actor
    user.status_note = (note or "")[:500]


def create_user(email, password, full_name, role=UserRole.SALES_USER, is_active=True, is_staff=False, is_superuser=False, password_hash=None, account_status=AccountStatus.APPROVED):
    """
    Create a new user in the system.

    Pass ``password_hash`` (from ``make_password``) instead of ``password`` when
    the raw password must not be kept around, e.g. during OTP signup.
    """
    if not email:
        raise DomainError("Email address is required.")
    
    if User.objects.filter(email=email).exists():
        raise DomainError(f"A user with email '{email}' already exists.")
        
    if role not in UserRole.values:
        raise DomainError(f"Invalid user role: '{role}'")

    # If the role is ADMIN, make sure they are staff
    staff_status = is_staff or (role == UserRole.ADMIN)

    if account_status not in AccountStatus.values:
        raise DomainError(f"Invalid account status: '{account_status}'")

    user = User.objects.create_user(
        email=email,
        password=password,
        full_name=full_name,
        role=role,
        is_active=is_active,
        is_staff=staff_status,
        is_superuser=is_superuser,
        account_status=account_status,
    )
    if password_hash:
        user.password = password_hash
        user.save(update_fields=["password"])
    return user


def activate_user(user, actor=None):
    """
    Activate a deactivated user. ``actor`` (the requesting user) is authorised
    when given; internal callers may omit it.
    """
    if actor is not None:
        check_can_manage(actor, user)
    if user.is_active:
        raise WorkflowError("User is already active.")
    user.is_active = True
    user.save()
    return user


def deactivate_user(user, actor=None):
    """
    Deactivate an active user.
    """
    if actor is not None:
        check_can_manage(actor, user)
    if not user.is_active:
        raise WorkflowError("User is already inactive.")
    
    # Prevent deactivating the last active admin
    if user.role == UserRole.ADMIN:
        if _active_admin_count() <= 1:
            raise WorkflowError("Cannot deactivate the last active Admin user.")
            
    user.is_active = False
    user.save()
    return user


def change_role(user, new_role, actor=None):
    """
    Change a user's role.
    """
    if new_role not in UserRole.values:
        raise DomainError(f"Invalid user role: '{new_role}'")
    if actor is not None:
        check_can_manage(actor, user, new_role=new_role)
        
    if user.role == new_role:
        raise WorkflowError(f"User is already assigned the '{new_role}' role.")

    # Prevent changing role of the last active admin
    if user.role == UserRole.ADMIN and new_role != UserRole.ADMIN:
        if _active_admin_count() <= 1:
            raise WorkflowError("Cannot change the role of the last active Admin user.")
            
    user.role = new_role
    # Django-admin (staff) access follows the ADMIN role, both ways; superusers keep theirs.
    user.is_staff = new_role == UserRole.ADMIN or user.is_superuser
    user.save()
    return user


# --- Approval workflow ---------------------------------------------------------------

def approve_user(user, role, actor):
    """Approve a PENDING (or previously REJECTED) account and grant it ``role``.

    The role must be chosen explicitly at approval time: signup never grants one.
    """
    if role not in UserRole.values:
        raise DomainError(f"Invalid user role: '{role}'")
    check_can_manage(actor, user, new_role=role)
    if user.account_status not in (AccountStatus.PENDING, AccountStatus.REJECTED):
        raise WorkflowError(f"Only pending or rejected accounts can be approved (this one is {user.get_account_status_display().lower()}).")
    user.role = role
    user.is_staff = role == UserRole.ADMIN
    _set_status(user, AccountStatus.APPROVED, actor)
    user.save()
    return user


def reject_user(user, actor, note=""):
    """Reject a PENDING account. It can never sign in unless later approved."""
    check_can_manage(actor, user)
    if user.account_status != AccountStatus.PENDING:
        raise WorkflowError("Only pending accounts can be rejected.")
    _set_status(user, AccountStatus.REJECTED, actor, note)
    user.save()
    return user


def suspend_user(user, actor, note=""):
    """Temporarily block an APPROVED account (existing sessions stop working at once)."""
    check_can_manage(actor, user)
    if user.account_status != AccountStatus.APPROVED:
        raise WorkflowError("Only approved accounts can be suspended.")
    if user.role == UserRole.ADMIN and _active_admin_count() <= 1:
        raise WorkflowError("Cannot suspend the last active Admin user.")
    _set_status(user, AccountStatus.SUSPENDED, actor, note)
    user.save()
    return user


def reinstate_user(user, actor):
    """Lift a suspension."""
    check_can_manage(actor, user)
    if user.account_status != AccountStatus.SUSPENDED:
        raise WorkflowError("Only suspended accounts can be reinstated.")
    _set_status(user, AccountStatus.APPROVED, actor)
    user.save()
    return user
