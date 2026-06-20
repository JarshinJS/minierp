from rest_framework import serializers

from core.exceptions import DomainError

from .models import PurchaseOrder, PurchaseOrderLine, Vendor


class VendorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vendor
        fields = ["id", "name", "code", "contact_name", "email", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class PurchaseOrderLineSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = PurchaseOrderLine
        fields = [
            "id",
            "product",
            "product_name",
            "product_sku",
            "quantity",
            "received_qty",
            "unit_price",
            "subtotal",
        ]
        read_only_fields = ["id", "received_qty", "subtotal"]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    lines = PurchaseOrderLineSerializer(many=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    vendor_name = serializers.CharField(source="vendor.name", read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            "id",
            "order_number",
            "vendor",
            "vendor_name",
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
            "vendor_name",
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

        from . import services

        try:
            return services.create_order(
                vendor=validated_data["vendor"],
                created_by=created_by,
                lines_data=[{
                    "product": line["product"],
                    "quantity": line["quantity"],
                    "unit_price": line["unit_price"],
                } for line in lines_data],
                notes=validated_data.get("notes", ""),
            )
        except DomainError as exc:
            raise serializers.ValidationError({"detail": exc.message})

    def update(self, instance, validated_data):
        lines_data = validated_data.pop("lines", None)

        from . import services

        try:
            order = services.update_order(
                instance,
                vendor=validated_data.get("vendor", instance.vendor),
                lines_data=[{
                    "product": line["product"],
                    "quantity": line["quantity"],
                    "unit_price": line["unit_price"],
                } for line in lines_data] if lines_data is not None else None,
                notes=validated_data.get("notes", instance.notes),
            )
            return order
        except (DomainError, Exception) as exc:
            if isinstance(exc, DomainError):
                raise serializers.ValidationError({"detail": exc.message})
            raise