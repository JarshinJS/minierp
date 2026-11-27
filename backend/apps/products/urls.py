"""
urls.py for the Products app.

The product pages are served by the Next.js frontend (data from /api/products/).
These names stay registered so the remaining Django templates can still link to
them with {% url %}; Django itself only redirects to the frontend.
"""
from django.urls import path

from core.views import FrontendPageView

app_name = "products"

urlpatterns = [
    path("list/", FrontendPageView.as_view(), name="product_list"),
    path("create/", FrontendPageView.as_view(), name="product_create"),
    path("<uuid:pk>/", FrontendPageView.as_view(), name="product_detail"),
    path("<uuid:pk>/edit/", FrontendPageView.as_view(), name="product_edit"),
]
