from django.contrib import admin
from .models import ProcurementRequest

class ProcurementRequestAdmin(admin.ModelAdmin):
    list_display = ("product", "quantity_needed", "status", "reference", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("product__name", "product__sku", "reference")

admin.site.register(ProcurementRequest, ProcurementRequestAdmin)
