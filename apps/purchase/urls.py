"""
urls.py for the Purchase app.

This module contains the urls logic for the Purchase functionality.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("vendors", views.VendorViewSet, basename="api_vendor")
router.register("orders", views.PurchaseOrderViewSet, basename="api_purchase_order")

app_name = "purchase"

urlpatterns = [
	path("api/", include(router.urls)),
	path("vendors/", views.VendorUIListView.as_view(), name="vendor_list"),
	path("orders/", views.PurchaseOrderUIListView.as_view(), name="purchase_order_list"),
	path("orders/create/", views.PurchaseOrderUICreateView.as_view(), name="purchase_order_create"),
	path("orders/<uuid:pk>/edit/", views.PurchaseOrderUIUpdateView.as_view(), name="purchase_order_edit"),
	path("orders/<uuid:pk>/confirm/", views.PurchaseOrderUIConfirmView.as_view(), name="purchase_order_confirm"),
	path("orders/<uuid:pk>/receive/", views.PurchaseOrderUIReceiveView.as_view(), name="purchase_order_receive"),
	path("orders/<uuid:pk>/cancel/", views.PurchaseOrderUICancelView.as_view(), name="purchase_order_cancel"),
]
