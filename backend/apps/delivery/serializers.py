from decimal import Decimal

from rest_framework import serializers

from apps.sales.models import SalesOrder, SalesOrderLine
from .models import DeliveryNote, DeliveryNoteLine


class DeliveryNoteLineSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(source="sales_order_line.product_id", read_only=True)
    product_sku = serializers.CharField(source="sales_order_line.product.sku", read_only=True)
    product_name = serializers.CharField(source="sales_order_line.product.name", read_only=True)

    class Meta:
        model = DeliveryNoteLine
        fields = ["id", "sales_order_line", "product_id", "product_sku", "product_name", "quantity"]
        read_only_fields = fields


class DeliveryNoteSerializer(serializers.ModelSerializer):
    sales_order_number = serializers.CharField(source="sales_order.order_number", read_only=True)
    customer_name = serializers.CharField(source="sales_order.customer_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    lines = DeliveryNoteLineSerializer(many=True, read_only=True)

    class Meta:
        model = DeliveryNote
        fields = [
            "id", "delivery_number", "sales_order", "sales_order_number", "customer_name",
            "status", "status_display", "dispatch_date", "notes",
            "created_by", "created_by_name", "created_at", "lines",
        ]
        read_only_fields = fields


class DeliveryLineInputSerializer(serializers.Serializer):
    sales_order_line = serializers.PrimaryKeyRelatedField(queryset=SalesOrderLine.objects.select_related("product"))
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))


class DeliveryNoteCreateSerializer(serializers.Serializer):
    """Create a delivery note. Omit ``lines`` to deliver everything still pending."""
    sales_order = serializers.PrimaryKeyRelatedField(queryset=SalesOrder.objects.all())
    lines = DeliveryLineInputSerializer(many=True, required=False)
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        order = attrs["sales_order"]
        for line in attrs.get("lines", []):
            if line["sales_order_line"].order_id != order.pk:
                raise serializers.ValidationError({"lines": "Every line must belong to the given sales order."})
        return attrs
