from rest_framework import serializers
from apps.products.models import Product
from .models import SalesOrder, SalesOrderLine

class SalesOrderLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = SalesOrderLine
        fields = [
            "id",
            "product",
            "product_name",
            "product_sku",
            "quantity",
            "delivered_qty",
            "unit_price",
            "subtotal",
        ]
        read_only_fields = ["id", "delivered_qty", "subtotal"]


class SalesOrderSerializer(serializers.ModelSerializer):
    lines = SalesOrderLineSerializer(many=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)

    class Meta:
        model = SalesOrder
        fields = [
            "id",
            "order_number",
            "customer_name",
            "status",
            "created_by",
            "created_by_name",
            "notes",
            "total_amount",
            "lines",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "order_number",
            "status",
            "created_by",
            "created_by_name",
            "total_amount",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        lines_data = validated_data.pop("lines")
        request = self.context.get("request")
        created_by = validated_data.get("created_by")
        if not created_by and request:
            created_by = request.user
            
        formatted_lines = []
        for line in lines_data:
            formatted_lines.append({
                "product": line["product"],
                "quantity": line["quantity"],
                "unit_price": line["unit_price"]
            })
            
        from . import services
        from core.exceptions import DomainError
        try:
            order = services.create_order(
                customer_name=validated_data["customer_name"],
                created_by=created_by,
                lines_data=formatted_lines,
                notes=validated_data.get("notes", "")
            )
            return order
        except DomainError as e:
            raise serializers.ValidationError({"detail": e.message})
