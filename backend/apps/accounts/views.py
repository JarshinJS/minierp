"""
views.py for the Accounts app.

Login, signup and email verification are served by the Next.js frontend
(frontend/src/app/(auth)) on top of accounts.api. What remains here is logout and
the Users & Roles page, which is still a Django page.
"""
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Case, IntegerField, Value, When
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import redirect
from django.views import View
from django.views.generic import ListView
from core.exceptions import DomainError, WorkflowError
from .permissions import RoleRequiredMixin
from .models import AccountStatus, UserRole
from . import services

User = get_user_model()


class LogoutView(View):
    """POST only: a GET logout would let any site log users out with a link."""
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        auth_logout(request)
        return redirect(settings.LOGOUT_REDIRECT_URL)


class UserListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER]

    def get_queryset(self):
        # Pending requests first, then by email for a stable list.
        return super().get_queryset().annotate(
            pending_first=Case(When(account_status=AccountStatus.PENDING, then=Value(0)),
                               default=Value(1), output_field=IntegerField()),
        ).order_by("pending_first", "email")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for member in context["users"]:
            _annotate_permissions(self.request.user, member)
        context["roles"] = assignable_roles(self.request.user)
        context["pending_count"] = sum(1 for u in context["users"] if u.account_status == AccountStatus.PENDING)
        return context


class UserToggleActiveView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER]

    def post(self, request, pk, *args, **kwargs):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return HttpResponseBadRequest("User not found.")

        if user == request.user:
            return HttpResponseBadRequest("You cannot change your own active status.")

        try:
            if user.is_active:
                services.deactivate_user(user, actor=request.user)
            else:
                services.activate_user(user, actor=request.user)
        except PermissionDenied as e:
            return HttpResponseForbidden(str(e))
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)

        # Return the updated row partial
        return render_row_partial(request, user)


class UserChangeRoleView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER]

    def post(self, request, pk, *args, **kwargs):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return HttpResponseBadRequest("User not found.")

        if user == request.user:
            return HttpResponseBadRequest("You cannot change your own role.")

        new_role = request.POST.get("role")
        try:
            services.change_role(user, new_role, actor=request.user)
        except PermissionDenied as e:
            return HttpResponseForbidden(str(e))
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)

        # Return the updated row partial
        return render_row_partial(request, user)


class UserStatusActionView(LoginRequiredMixin, RoleRequiredMixin, View):
    """POST approve / reject / suspend / reinstate for one account; re-renders its row."""
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER]
    ACTIONS = {"approve", "reject", "suspend", "reinstate"}

    def post(self, request, pk, action, *args, **kwargs):
        if action not in self.ACTIONS:
            return HttpResponseBadRequest("Unknown action.")
        user = User.objects.filter(pk=pk).first()
        if user is None:
            return HttpResponseBadRequest("User not found.")
        note = request.POST.get("note", "")
        try:
            if action == "approve":
                services.approve_user(user, request.POST.get("role"), actor=request.user)
            elif action == "reject":
                services.reject_user(user, actor=request.user, note=note)
            elif action == "suspend":
                services.suspend_user(user, actor=request.user, note=note)
            else:
                services.reinstate_user(user, actor=request.user)
        except PermissionDenied as e:
            return HttpResponseForbidden(str(e))
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)
        return render_row_partial(request, user)


def assignable_roles(actor):
    """Roles ``actor`` may grant: everything for an Admin, non-privileged roles otherwise."""
    if actor.role == UserRole.ADMIN:
        return UserRole.choices
    return [(v, l) for v, l in UserRole.choices if v not in services.PRIVILEGED_ROLES]


def _annotate_permissions(actor, member):
    try:
        services.check_can_manage(actor, member)
        member.can_manage = True
    except PermissionDenied:
        member.can_manage = False
    return member


def render_row_partial(request, user):
    """
    Helper function to render a user table row inline using templates/accounts/user_row.html.
    """
    from django.shortcuts import render
    return render(
        request,
        "accounts/user_row.html",
        {"member": _annotate_permissions(request.user, user), "roles": assignable_roles(request.user)}
    )
