from django.contrib import admin

from .models import BoM, ManufacturingOrder

class BoMAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")

class ManufacturingOrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "product", "quantity", "status", "reference", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("order_number", "product__name", "product__sku", "reference")

admin.site.register(BoM, BoMAdmin)
admin.site.register(ManufacturingOrder, ManufacturingOrderAdmin)
