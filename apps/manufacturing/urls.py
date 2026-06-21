"""
urls.py for the Manufacturing app.

This module contains the urls logic for the Manufacturing functionality.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register("boms",           views.BOMViewSet,                    basename="api_bom")
router.register("workcenters",    views.WorkCenterViewSet,             basename="api_workcenter")
router.register("orders",         views.ManufacturingOrderViewSet,     basename="api_mo")
router.register("work-orders",    views.WorkOrderViewSet,              basename="api_wo")

app_name = "manufacturing"

urlpatterns = [
    # DRF API
    path("api/", include(router.urls)),

    # -----------------------------------------------------------------------
    # BOM UI Routes
    # -----------------------------------------------------------------------
    path("boms/",                           views.BOMListView.as_view(),        name="bom_list"),
    path("boms/create/",                    views.BOMCreateView.as_view(),      name="bom_create"),
    path("boms/<uuid:pk>/",                 views.BOMDetailView.as_view(),      name="bom_detail"),
    path("boms/<uuid:pk>/edit/",            views.BOMUpdateView.as_view(),      name="bom_edit"),
    path("boms/<uuid:pk>/deactivate/",      views.BOMDeactivateView.as_view(),  name="bom_deactivate"),

    # -----------------------------------------------------------------------
    # WorkCenter UI Routes
    # -----------------------------------------------------------------------
    path("workcenters/",                    views.WorkCenterListView.as_view(),   name="workcenter_list"),
    path("workcenters/create/",             views.WorkCenterCreateView.as_view(), name="workcenter_create"),
    path("workcenters/<uuid:pk>/edit/",     views.WorkCenterUpdateView.as_view(), name="workcenter_edit"),

    # -----------------------------------------------------------------------
    # Manufacturing Order UI Routes
    # -----------------------------------------------------------------------
    path("orders/",                         views.MOListView.as_view(),         name="mo_list"),
    path("orders/create/",                  views.MOCreateView.as_view(),       name="mo_create"),
    path("orders/<uuid:pk>/",               views.MODetailView.as_view(),       name="mo_detail"),
    path("orders/<uuid:pk>/edit/",          views.MOUpdateView.as_view(),       name="mo_edit"),
    path("orders/<uuid:pk>/confirm/",       views.MOConfirmView.as_view(),      name="mo_confirm"),
    path("orders/<uuid:pk>/start/",         views.MOStartView.as_view(),        name="mo_start"),
    path("orders/<uuid:pk>/produce/",       views.MOProduceView.as_view(),      name="mo_produce"),
    path("orders/<uuid:pk>/cancel/",        views.MOCancelView.as_view(),       name="mo_cancel"),

    # -----------------------------------------------------------------------
    # Work Order Action Routes
    # -----------------------------------------------------------------------
    path("work-orders/<uuid:pk>/start/",    views.WorkOrderStartView.as_view(), name="wo_start"),
    path("work-orders/<uuid:pk>/complete/", views.WorkOrderCompleteView.as_view(), name="wo_complete"),
]
