from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from rest_framework import permissions

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
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        # ADMIN bypasses all role constraints
        if request.user.role == "ADMIN":
            return True

        allowed_roles = getattr(view, "allowed_roles", None)
        if allowed_roles is None:
            return False

        return request.user.role in allowed_roles
