from django.contrib import admin
from .models import InventoryLedgerEntry

class InventoryLedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("product", "quantity", "entry_type", "reference", "created_at")
    list_filter = ("entry_type", "created_at")
    search_fields = ("product__name", "product__sku", "reference")
    readonly_fields = ("product", "quantity", "entry_type", "reference")

admin.site.register(InventoryLedgerEntry, InventoryLedgerEntryAdmin)
