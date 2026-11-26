from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from rest_framework import permissions

from .models import UserRole

# Single source of truth for which roles may use which module. The sidebar,
# the HTML views (via RoleRequiredMixin) and the DRF APIs (via
# DRFRolePermission) all derive their access rules from this mapping.
MODULE_ACCESS = {
    UserRole.ADMIN: ["dashboard", "accounts", "products", "inventory", "sales", "purchase", "manufacturing", "procurement", "delivery", "reports", "audit_logs", "foreign_trade", "blockchain"],
    UserRole.BUSINESS_OWNER: ["dashboard", "accounts", "products", "inventory", "sales", "purchase", "manufacturing", "procurement", "delivery", "reports", "audit_logs", "foreign_trade", "blockchain"],
    UserRole.SALES_USER: ["dashboard", "sales", "products", "delivery"],
    UserRole.PURCHASE_USER: ["dashboard", "purchase", "products", "procurement"],
    UserRole.MANUFACTURING_USER: ["dashboard", "manufacturing", "inventory"],
    UserRole.INVENTORY_MANAGER: ["dashboard", "inventory", "products", "procurement", "delivery"],
    UserRole.ACCOUNTANT: ["dashboard", "reports"],
    UserRole.TRADE_MANAGER: ["dashboard", "foreign_trade", "blockchain", "reports"],
    UserRole.DOCUMENTATION_OFFICER: ["dashboard", "foreign_trade", "blockchain"],
    UserRole.FINANCE_MANAGER: ["dashboard", "foreign_trade", "reports"],
    UserRole.AUDITOR: ["dashboard", "foreign_trade", "blockchain", "audit_logs", "reports"],
}


def roles_for_module(module):
    """Return the list of roles allowed to access ``module``."""
    return [role for role, modules in MODULE_ACCESS.items() if module in modules]


def can_access_module(user, module):
    """True if ``user`` is authenticated and their role grants ``module``."""
    if not user or not user.is_authenticated:
        return False
    if user.role == UserRole.ADMIN:
        return True
    return module in MODULE_ACCESS.get(user.role, [])

class RoleRequiredMixin(AccessMixin):
    """
    Django Class-Based View mixin that restricts access to users with specific roles.
    Always allows ADMIN role to bypass constraints.
    """
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
            
        # If allowed_roles is not configured, deny by default to be secure
        if not self.allowed_roles:
            raise PermissionDenied("View permission configuration missing.")

        # ADMIN bypasses all role constraints
        if request.user.role == "ADMIN" or request.user.role in self.allowed_roles:
            return super().dispatch(request, *args, **kwargs)
            
        raise PermissionDenied("You do not have permission to access this resource.")


class DRFRolePermission(permissions.BasePermission):
    """
    Django REST Framework permission that checks if the authenticated user has an allowed role.
    Always allows ADMIN role to bypass constraints.

    Roles are resolved from the view, most specific first:
      1. ``action_roles[view.action]``  (e.g. {"dispatch": [...]})
      2. ``read_roles`` for GET/HEAD/OPTIONS
      3. ``allowed_roles``
    If none is configured, access is denied.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # ADMIN bypasses all role constraints
        if request.user.role == "ADMIN":
            return True

        allowed_roles = self._resolve_roles(request, view)
        if allowed_roles is None:
            return False

        return request.user.role in allowed_roles

    @staticmethod
    def _resolve_roles(request, view):
        action_roles = getattr(view, "action_roles", None) or {}
        action = getattr(view, "action", None)
        if action in action_roles:
            return action_roles[action]
        read_roles = getattr(view, "read_roles", None)
        if read_roles is not None and request.method in permissions.SAFE_METHODS:
            return read_roles
        return getattr(view, "allowed_roles", None)
