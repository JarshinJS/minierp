from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView
from core.exceptions import DomainError, WorkflowError
from .forms import SignupForm, LoginForm
from .permissions import RoleRequiredMixin
from .models import UserRole
from . import services

User = get_user_model()

class SignupView(FormView):
    template_name = "accounts/signup.html"
    form_class = SignupForm
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        try:
            services.create_user(
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
                full_name=form.cleaned_data["full_name"],
                role=form.cleaned_data["role"],
            )
            return super().form_valid(form)
        except DomainError as e:
            form.add_error(None, e.message)
            return self.form_invalid(form)


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
