from django.contrib import admin
from .models import BoM

class BoMAdmin(admin.ModelAdmin):
    list_display = ("name", "code")
    search_fields = ("name", "code")

admin.site.register(BoM, BoMAdmin)
