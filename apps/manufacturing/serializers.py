from rest_framework import serializers
from .models import BoM, BOMComponent, BOMOperation, WorkCenter


class WorkCenterSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkCenter
        fields = ["id", "name", "code", "cost_per_hour", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class BOMComponentSerializer(serializers.ModelSerializer):
    component_name = serializers.CharField(source="component.name", read_only=True)
    component_sku = serializers.CharField(source="component.sku", read_only=True)

    class Meta:
        model = BOMComponent
        fields = [
            "id", "component", "component_name", "component_sku",
            "quantity", "uom", "sequence",
        ]
        read_only_fields = ["id"]


class BOMOperationSerializer(serializers.ModelSerializer):
    work_center_name = serializers.CharField(source="work_center.name", read_only=True)

    class Meta:
        model = BOMOperation
        fields = [
            "id", "work_center", "work_center_name",
            "name", "duration_minutes", "sequence",
        ]
        read_only_fields = ["id"]


class BOMSerializer(serializers.ModelSerializer):
    components = BOMComponentSerializer(many=True, read_only=True)
    operations = BOMOperationSerializer(many=True, read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True, allow_null=True)
    total_material_cost = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )

    class Meta:
        model = BoM
        fields = [
            "id", "name", "reference", "product", "product_name",
            "product_qty", "is_active", "notes",
            "components", "operations", "total_material_cost",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "total_material_cost"]


class BOMWriteSerializer(serializers.ModelSerializer):
    """
    Write serializer — accepts flat header fields only.
    Components and operations are managed separately via the service layer.
    """
    class Meta:
        model = BoM
        fields = ["name", "reference", "product", "product_qty", "notes"]
