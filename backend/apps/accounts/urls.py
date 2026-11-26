"""
urls.py for the Accounts app.

This module contains the urls logic for the Accounts functionality.
"""
from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.SignupView.as_view(), name="signup"),
    path("verify-otp/", views.VerifyOTPView.as_view(), name="verify_otp"),
    path("resend-otp/", views.ResendOTPView.as_view(), name="resend_otp"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/<uuid:pk>/toggle-active/", views.UserToggleActiveView.as_view(), name="toggle_active"),
    path("users/<uuid:pk>/change-role/", views.UserChangeRoleView.as_view(), name="change_role"),
]
