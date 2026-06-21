"""
admin.py for the Foreign_trade app.

This module contains the admin logic for the Foreign_trade functionality.
"""
from django.contrib import admin
from .models import (
    Country, Currency, Incoterm,
    TradeCustomer, TradeSupplier,
    ExportOrder, ExportOrderLine, ExportInvoice,
    ImportOrder, ImportOrderLine,
    Shipment, TradeDocument,
)


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "region")
    search_fields = ("name", "code")
    list_filter = ("region",)


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "symbol", "exchange_rate")
    search_fields = ("code", "name")


@admin.register(Incoterm)
class IncotermAdmin(admin.ModelAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")


@admin.register(TradeCustomer)
class TradeCustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "email", "is_active")
    search_fields = ("name", "email", "tax_id")
    list_filter = ("is_active", "country")


@admin.register(TradeSupplier)
class TradeSupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "country", "email", "is_active")
    search_fields = ("name", "email", "tax_id")
    list_filter = ("is_active", "country")


class ExportOrderLineInline(admin.TabularInline):
    model = ExportOrderLine
    extra = 1


@admin.register(ExportOrder)
class ExportOrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "customer", "country", "status", "created_at")
    search_fields = ("order_number", "customer__name")
    list_filter = ("status", "shipping_method", "country")
    inlines = [ExportOrderLineInline]


@admin.register(ExportInvoice)
class ExportInvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoice_number", "export_order", "amount", "status", "due_date")
    search_fields = ("invoice_number",)
    list_filter = ("status",)


class ImportOrderLineInline(admin.TabularInline):
    model = ImportOrderLine
    extra = 1


@admin.register(ImportOrder)
class ImportOrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "supplier", "country", "status", "customs_status", "created_at")
    search_fields = ("order_number", "supplier__name")
    list_filter = ("status", "customs_status", "country")
    inlines = [ImportOrderLineInline]


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ("shipment_number", "carrier", "status", "departure_date", "arrival_date")
    search_fields = ("shipment_number", "tracking_number", "carrier")
    list_filter = ("status",)


@admin.register(TradeDocument)
class TradeDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "document_type", "version", "verification_status", "uploaded_by", "created_at")
    search_fields = ("title",)
    list_filter = ("document_type", "verification_status")
