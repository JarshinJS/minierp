"""
models.py for the Audit_logs app.

This module contains the models logic for the Audit_logs functionality.
"""
import uuid

from django.conf import settings
from django.db import models

from core.models import UUIDBaseModel, TimeStampedModel


class AuditLogAction(models.TextChoices):
	CREATED = "created", "Created"
	UPDATED = "updated", "Updated"
	DELETED = "deleted", "Deleted"
	STATUS_CHANGED = "status_changed", "Status Changed"
	PRICE_CHANGED = "price_changed", "Price Changed"
	STOCK_ADJUSTED = "stock_adjusted", "Stock Adjusted"
	AUTO_CREATED = "auto_created", "Auto Created"


class AuditLog(UUIDBaseModel, TimeStampedModel):
	user = models.ForeignKey(
		settings.AUTH_USER_MODEL,
		null=True,
		blank=True,
		on_delete=models.SET_NULL,
		related_name="audit_logs",
	)
	module = models.CharField(max_length=64, db_index=True)
	record_type = models.CharField(max_length=64, db_index=True)
	record_id = models.UUIDField(db_index=True)
	action = models.CharField(max_length=32, choices=AuditLogAction.choices, db_index=True)
	field_changed = models.CharField(max_length=128, blank=True)
	old_value = models.TextField(blank=True)
	new_value = models.TextField(blank=True)
	timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

	class Meta:
		ordering = ["-timestamp", "-created_at"]
		indexes = [
			models.Index(fields=["module", "action", "timestamp"]),
			models.Index(fields=["record_type", "record_id"]),
		]

	def __str__(self):
		return f"{self.module}:{self.record_type}:{self.record_id} [{self.action}]"
