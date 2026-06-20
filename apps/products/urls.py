from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("products", views.ProductViewSet, basename="api_product")
router.register("categories", views.CategoryViewSet, basename="api_category")

app_name = "products"

urlpatterns = [
    # API Router prefix
    path("api/", include(router.urls)),

    # UI Routes
    path("list/", views.ProductUIListView.as_view(), name="product_list"),
    path("create/", views.ProductUICreateView.as_view(), name="product_create"),
    path("<uuid:pk>/", views.ProductUIDetailView.as_view(), name="product_detail"),
    path("<uuid:pk>/edit/", views.ProductUIUpdateView.as_view(), name="product_edit"),
    path("<uuid:pk>/deactivate/", views.ProductUIDeactivateView.as_view(), name="product_deactivate"),
]
