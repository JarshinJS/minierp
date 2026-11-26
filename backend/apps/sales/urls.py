"""
urls.py for the Sales app.

This module contains the urls logic for the Sales functionality.
"""
from django.urls import path
from . import views


app_name = "sales"

urlpatterns = [
    # API Router

    # UI Routes
    path("list/", views.SalesOrderUIListView.as_view(), name="sales_order_list"),
    path("kanban/", views.SalesOrderUIKanbanView.as_view(), name="sales_order_kanban"),
    path("create/", views.SalesOrderUICreateView.as_view(), name="sales_order_create"),
    path("<uuid:pk>/", views.SalesOrderUIDetailView.as_view(), name="sales_order_detail"),
    path("<uuid:pk>/edit/", views.SalesOrderUIUpdateView.as_view(), name="sales_order_edit"),
    
    # HTMX Actions
    path("<uuid:pk>/confirm/", views.SalesOrderUIConfirmView.as_view(), name="sales_order_confirm"),
    path("<uuid:pk>/deliver/", views.SalesOrderUIDeliverView.as_view(), name="sales_order_deliver"),
    path("<uuid:pk>/cancel/", views.SalesOrderUICancelView.as_view(), name="sales_order_cancel"),
]
