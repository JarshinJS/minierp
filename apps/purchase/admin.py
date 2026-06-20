from django.contrib import admin
from .models import Vendor

class VendorAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "email")
    search_fields = ("name", "code")

admin.site.register(Vendor, VendorAdmin)
