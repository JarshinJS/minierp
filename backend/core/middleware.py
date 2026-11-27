"""
Account-status gate for every request.

Authenticated sessions belonging to accounts that are not approved (pending,
rejected, suspended) or no longer active are ended here, before any view runs,
so no endpoint can forget the check. Per-view permissions (DRFRolePermission,
RoleRequiredMixin, IsApprovedUser) check the same thing again.
"""
from django.contrib.auth import logout
from django.http import HttpResponseForbidden, JsonResponse

from apps.accounts.permissions import ACCOUNT_STATUS_MESSAGES, account_block_code


class AccountStatusMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            code = account_block_code(user)
            if code is not None:
                return self._blocked(request, code)
        return self.get_response(request)

    @staticmethod
    def _blocked(request, code):
        message = ACCOUNT_STATUS_MESSAGES[code]
        # End the session: a blocked account must not keep an authenticated session.
        logout(request)
        if request.path.startswith("/api/"):
            return JsonResponse({"detail": message, "code": code}, status=403)
        return HttpResponseForbidden(message)
