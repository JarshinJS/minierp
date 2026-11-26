"""
admin.py for the Audit_logs app.

This module contains the admin logic for the Audit_logs functionality.
"""
from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
	list_display = (
		"timestamp",
		"user",
		"module",
		"record_type",
		"record_id",
		"action",
		"field_changed",
	)
	list_filter = ("module", "action", "record_type", "timestamp")
	search_fields = ("module", "record_type", "field_changed", "old_value", "new_value")
