"""
views.py for the Accounts app.

This module contains the views logic for the Accounts functionality.
"""
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView
from core.exceptions import DomainError, WorkflowError
from .forms import SignupForm, LoginForm, VerifyOTPForm
from .permissions import RoleRequiredMixin
from .models import UserRole
from . import services
from . import signup

User = get_user_model()


def _add_signup_error(form, error):
    field = error.field if error.field in form.fields else None
    form.add_error(field, error.message)


class SignupView(FormView):
    template_name = "accounts/signup.html"
    form_class = SignupForm
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        try:
            signup.start_signup(
                self.request.session,
                email=form.cleaned_data["email"],
                full_name=form.cleaned_data["full_name"],
                password=form.cleaned_data["password"],
            )
        except signup.SignupError as e:
            _add_signup_error(form, e)
            return self.form_invalid(form)
        return redirect("accounts:verify_otp")


class VerifyOTPView(FormView):
    template_name = "accounts/verify_otp.html"
    form_class = VerifyOTPForm
    success_url = reverse_lazy("accounts:login")

    def dispatch(self, request, *args, **kwargs):
        # Redirect to signup if there is no signup data in the session
        if signup.pending_signup(request.session) is None:
            return redirect("accounts:signup")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        signup_data = signup.pending_signup(self.request.session) or {}
        context["email"] = signup_data.get("email", "")
        # Add the expiry time for the UI countdown
        context["otp_expiry"] = signup_data.get("otp_expiry", 0)
        context["resent"] = self.request.GET.get("resent") == "1"
        return context

    def form_valid(self, form):
        try:
            signup.verify_signup(self.request.session, form.cleaned_data["otp"])
        except signup.SignupError as e:
            if e.restart:
                messages.error(self.request, e.message)
                return redirect("accounts:signup")
            _add_signup_error(form, e)
            return self.form_invalid(form)
        return super().form_valid(form)


class ResendOTPView(View):
    def post(self, request, *args, **kwargs):
        try:
            signup.resend_otp(request.session)
        except signup.SignupError as e:
            messages.error(request, e.message)
            if e.restart:
                return redirect("accounts:signup")
            return redirect("accounts:verify_otp")
        return redirect(reverse("accounts:verify_otp") + "?resent=1")


class LoginView(FormView):
    template_name = "accounts/login.html"
    form_class = LoginForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        return kwargs

    def get_success_url(self):
        # Redirect based on user role to make a premium UX
        user = self.request.user
        if user.role in [UserRole.ADMIN, UserRole.BUSINESS_OWNER]:
            return reverse_lazy("accounts:user_list")
        return reverse_lazy("dashboard:home")

    def form_valid(self, form):
        auth_login(self.request, form.get_user())
        return super().form_valid(form)


class LogoutView(View):
    def post(self, request, *args, **kwargs):
        auth_logout(request)
        return redirect("accounts:login")

    def get(self, request, *args, **kwargs):
        # Fallback for GET request logouts
        auth_logout(request)
        return redirect("accounts:login")


class UserListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = User
    template_name = "accounts/user_list.html"
    context_object_name = "users"
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER]

    def get_queryset(self):
        queryset = super().get_queryset()
        # Sort users by email for a stable view list
        return queryset.order_by("email")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["roles"] = UserRole.choices
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
                services.deactivate_user(user)
            else:
                services.activate_user(user)
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
            services.change_role(user, new_role)
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)

        # Return the updated row partial
        return render_row_partial(request, user)


# Dummy Dashboard view to support routing redirects for non-admin users
class DashboardHomeView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return redirect(reverse_lazy("dashboard:home"))


def render_row_partial(request, user):
    """
    Helper function to render a user table row inline using templates/accounts/user_row.html.
    """
    from django.shortcuts import render
    return render(
        request,
        "accounts/user_row.html",
        {"member": user, "roles": UserRole.choices}
    )
