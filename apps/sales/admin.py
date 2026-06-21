"""
admin.py for the Sales app.

This module contains the admin logic for the Sales functionality.
"""
from django.contrib import admin
from .models import SalesOrder, SalesOrderLine

class SalesOrderLineInline(admin.TabularInline):
    model = SalesOrderLine
    extra = 1
    readonly_fields = ("delivered_qty",)


class SalesOrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "customer_name", "status", "total_amount", "created_by", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("order_number", "customer_name")
    readonly_fields = ("order_number", "created_by")
    inlines = [SalesOrderLineInline]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

admin.site.register(SalesOrder, SalesOrderAdmin)
