from decimal import Decimal

from rest_framework import serializers

from apps.products.models import Product
from .models import InventoryLedgerEntry, LedgerEntryType


class StockLevelSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    avail_qty = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    cost_value = serializers.DecimalField(max_digits=16, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id", "sku", "name", "category", "category_name", "unit_of_measure",
            "on_hand_qty", "reserved_qty", "avail_qty", "cost_price", "cost_value",
        ]
        read_only_fields = fields


class InventoryStatsSerializer(serializers.Serializer):
    total_skus = serializers.IntegerField()
    total_items = serializers.DecimalField(max_digits=16, decimal_places=2)
    total_value = serializers.DecimalField(max_digits=18, decimal_places=2)
    out_of_stock = serializers.IntegerField()
    low_stock = serializers.IntegerField()


class LedgerEntrySerializer(serializers.ModelSerializer):
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    entry_type_display = serializers.CharField(source="get_entry_type_display", read_only=True)

    class Meta:
        model = InventoryLedgerEntry
        fields = [
            "id", "product", "product_sku", "product_name", "entry_type", "entry_type_display",
            "quantity", "reference", "created_at",
        ]
        read_only_fields = fields


class StockAdjustmentSerializer(serializers.Serializer):
    """Manual stock adjustment: RECEIPT adds stock, ISSUE removes it."""
    product = serializers.PrimaryKeyRelatedField(queryset=Product.objects.all())
    adjustment_type = serializers.ChoiceField(choices=[
        (LedgerEntryType.RECEIPT, "Receipt"), (LedgerEntryType.ISSUE, "Issue"),
    ])
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    reference = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
