"""
urls.py for the Delivery app.

This module contains the urls logic for the Delivery functionality.
"""
from django.urls import path
from . import views

app_name = "delivery"

urlpatterns = [
    path("", views.DeliveryUIListView.as_view(), name="list"),
    path("<uuid:pk>/", views.DeliveryUIDetailView.as_view(), name="detail"),
    path("create/<uuid:pk>/", views.DeliveryUICreateView.as_view(), name="create"),
    path("<uuid:pk>/dispatch/", views.DeliveryUIDispatchView.as_view(), name="dispatch"),
    path("<uuid:pk>/deliver/", views.DeliveryUIDeliverView.as_view(), name="deliver"),
]
