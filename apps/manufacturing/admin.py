"""
admin.py for the Manufacturing app.

This module contains the admin logic for the Manufacturing functionality.
"""
from django.contrib import admin
from .models import BoM, BOMComponent, BOMOperation, WorkCenter, ManufacturingOrder, MOComponent, WorkOrder


class BOMComponentInline(admin.TabularInline):
    model = BOMComponent
    extra = 1
    fields = ["sequence", "component", "quantity", "uom"]
    ordering = ["sequence"]


class BOMOperationInline(admin.TabularInline):
    model = BOMOperation
    extra = 1
    fields = ["sequence", "work_center", "name", "duration_minutes"]
    ordering = ["sequence"]


@admin.register(BoM)
class BoMAdmin(admin.ModelAdmin):
    list_display = ["reference", "name", "product", "product_qty", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "reference"]
    ordering = ["reference"]
    inlines = [BOMComponentInline, BOMOperationInline]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(WorkCenter)
class WorkCenterAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "cost_per_hour", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["name", "code"]
    ordering = ["name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(BOMComponent)
class BOMComponentAdmin(admin.ModelAdmin):
    list_display = ["bom", "component", "quantity", "uom", "sequence"]
    list_select_related = ["bom", "component"]
    ordering = ["bom__reference", "sequence"]


@admin.register(BOMOperation)
class BOMOperationAdmin(admin.ModelAdmin):
    list_display = ["bom", "sequence", "name", "work_center", "duration_minutes"]
    list_select_related = ["bom", "work_center"]
    ordering = ["bom__reference", "sequence"]


# ===========================================================================
# Manufacturing Order Admin
# ===========================================================================

class MOComponentInline(admin.TabularInline):
    model = MOComponent
    extra = 0
    fields = ["sequence", "product", "qty_required", "qty_consumed", "uom"]
    readonly_fields = ["qty_consumed"]
    ordering = ["sequence"]


class WorkOrderInline(admin.TabularInline):
    model = WorkOrder
    extra = 0
    fields = ["sequence", "work_center", "name", "duration_expected", "duration_actual", "status"]
    ordering = ["sequence"]


@admin.register(ManufacturingOrder)
class ManufacturingOrderAdmin(admin.ModelAdmin):
    list_display = ["reference", "product", "qty_to_produce", "qty_produced", "status", "scheduled_date", "created_at"]
    list_filter  = ["status"]
    search_fields = ["reference", "product__name", "product__sku"]
    ordering     = ["-created_at"]
    readonly_fields = ["reference", "qty_produced", "created_at", "updated_at"]
    inlines      = [MOComponentInline, WorkOrderInline]


@admin.register(MOComponent)
class MOComponentAdmin(admin.ModelAdmin):
    list_display = ["mo", "product", "qty_required", "qty_consumed", "uom"]
    list_select_related = ["mo", "product"]


@admin.register(WorkOrder)
class WorkOrderAdmin(admin.ModelAdmin):
    list_display = ["mo", "sequence", "name", "work_center", "duration_expected", "duration_actual", "status"]
    list_filter  = ["status"]
    list_select_related = ["mo", "work_center"]
    ordering = ["mo__reference", "sequence"]
