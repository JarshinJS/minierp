"""
admin.py for the Products app.

This module contains the admin logic for the Products functionality.
"""
from django.contrib import admin
from .models import Category, Product

class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    search_fields = ("name",)


class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sku",
        "category",
        "unit_of_measure",
        "selling_price",
        "cost_price",
        "on_hand_qty",
        "reserved_qty",
        "is_active",
    )
    search_fields = ("name", "sku")
    list_filter = ("category", "unit_of_measure", "is_active")
    
    # Read-only fields in admin view as well, ensuring consistency
    readonly_fields = ("on_hand_qty", "reserved_qty")
    
    fieldsets = (
        (None, {"fields": ("name", "sku", "category", "unit_of_measure", "is_active")}),
        ("Pricing Info", {"fields": ("selling_price", "cost_price")}),
        ("Stock Levels (Read-only)", {"fields": ("on_hand_qty", "reserved_qty")}),
        ("Sourcing Details", {"fields": ("procure_on_demand", "procurement_type", "default_vendor", "default_bom")}),
    )

admin.site.register(Category, CategoryAdmin)
admin.site.register(Product, ProductAdmin)
