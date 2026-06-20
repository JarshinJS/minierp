from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("boms", views.BOMViewSet, basename="api_bom")
router.register("workcenters", views.WorkCenterViewSet, basename="api_workcenter")

app_name = "manufacturing"

urlpatterns = [
    # DRF API
    path("api/", include(router.urls)),

    # BOM UI Routes
    path("boms/", views.BOMListView.as_view(), name="bom_list"),
    path("boms/create/", views.BOMCreateView.as_view(), name="bom_create"),
    path("boms/<uuid:pk>/", views.BOMDetailView.as_view(), name="bom_detail"),
    path("boms/<uuid:pk>/edit/", views.BOMUpdateView.as_view(), name="bom_edit"),
    path("boms/<uuid:pk>/deactivate/", views.BOMDeactivateView.as_view(), name="bom_deactivate"),

    # WorkCenter UI Routes
    path("workcenters/", views.WorkCenterListView.as_view(), name="workcenter_list"),
    path("workcenters/create/", views.WorkCenterCreateView.as_view(), name="workcenter_create"),
    path("workcenters/<uuid:pk>/edit/", views.WorkCenterUpdateView.as_view(), name="workcenter_edit"),
]
