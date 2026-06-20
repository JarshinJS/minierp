from django.contrib import admin
from .models import BoM, BOMComponent, BOMOperation, WorkCenter


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
