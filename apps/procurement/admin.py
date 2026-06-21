"""
admin.py for the Procurement app.

This module contains the admin logic for the Procurement functionality.
"""
from django.contrib import admin

from .models import ProcurementRequest, ProcurementTrigger

class ProcurementRequestAdmin(admin.ModelAdmin):
    list_display = ("product", "quantity_needed", "status", "reference", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("product__name", "product__sku", "reference")

@admin.register(ProcurementTrigger)
class ProcurementTriggerAdmin(admin.ModelAdmin):
    list_display = ("product", "quantity_needed", "status", "document_type", "document_number", "reference", "created_at")
    list_filter = ("status", "document_type", "created_at")
    search_fields = ("product__name", "product__sku", "reference", "document_number")

admin.site.register(ProcurementRequest, ProcurementRequestAdmin)
