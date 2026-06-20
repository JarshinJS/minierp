from django.contrib import admin
from .models import StockLedger


@admin.register(StockLedger)
class StockLedgerAdmin(admin.ModelAdmin):
	list_display = (
		"created_at",
		"product",
		"movement_type",
		"direction",
		"quantity",
		"reference_type",
		"reference_id",
	)
	list_filter = ("movement_type", "direction", "reference_type", "created_at")
	search_fields = ("product__name", "reference_type", "reference_id")
