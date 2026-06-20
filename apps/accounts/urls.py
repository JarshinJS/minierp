from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("signup/", views.SignupView.as_view(), name="signup"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("users/", views.UserListView.as_view(), name="user_list"),
    path("users/<uuid:pk>/toggle-active/", views.UserToggleActiveView.as_view(), name="toggle_active"),
    path("users/<uuid:pk>/change-role/", views.UserChangeRoleView.as_view(), name="change_role"),
    path("dashboard/", views.DashboardHomeView.as_view(), name="dashboard_home"),
]
