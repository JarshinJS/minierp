import uuid

from django.db import models

from core.models import UUIDBaseModel, TimeStampedModel

from apps.products.models import Product


class StockMovementType(models.TextChoices):
	PURCHASE_RECEIPT = "purchase_receipt", "Purchase Receipt"
	SALE_DELIVERY = "sale_delivery", "Sale Delivery"
	MO_CONSUMPTION = "mo_consumption", "MO Consumption"
	MO_PRODUCTION = "mo_production", "MO Production"
	ADJUSTMENT = "adjustment", "Adjustment"


class StockDirection(models.TextChoices):
	IN = "in", "In"
	OUT = "out", "Out"


class StockLedger(UUIDBaseModel, TimeStampedModel):
	product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_ledger_entries")
	movement_type = models.CharField(max_length=32, choices=StockMovementType.choices, db_index=True)
	quantity = models.DecimalField(max_digits=12, decimal_places=2)
	direction = models.CharField(max_length=3, choices=StockDirection.choices, db_index=True)
	reference_type = models.CharField(max_length=64, blank=True, db_index=True)
	reference_id = models.UUIDField(null=True, blank=True, db_index=True)

	class Meta:
		ordering = ["-created_at"]
		indexes = [
			models.Index(fields=["product", "created_at"]),
			models.Index(fields=["movement_type", "direction"]),
		]

	def __str__(self):
		return f"{self.product_id}:{self.movement_type}:{self.direction}:{self.quantity}"
