"""
admin.py for the Purchase app.

This module contains the admin logic for the Purchase functionality.
"""
from django.contrib import admin

from .models import PurchaseOrder, PurchaseOrderLine, Vendor


class PurchaseOrderLineInline(admin.TabularInline):
    model = PurchaseOrderLine
    extra = 1
    readonly_fields = ("received_qty",)


class VendorAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "contact_name", "email")
    search_fields = ("name", "code", "contact_name", "email")


class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "vendor", "status", "total_amount", "created_by", "created_at")
    list_filter = ("status", "created_at", "vendor")
    search_fields = ("order_number", "vendor__name", "vendor__code")
    readonly_fields = ("order_number", "created_by")
    inlines = [PurchaseOrderLineInline]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


admin.site.register(Vendor, VendorAdmin)
admin.site.register(PurchaseOrder, PurchaseOrderAdmin)
