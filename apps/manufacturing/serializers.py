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
        fields = ["id", "name", "reference", "product", "product_qty", "notes"]
        read_only_fields = ["id"]


# ===========================================================================
# Manufacturing Order Serializers
# ===========================================================================

from .models import ManufacturingOrder, MOComponent, WorkOrder, MOStatus, WorkOrderStatus


class MOComponentSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku  = serializers.CharField(source="product.sku",  read_only=True)

    class Meta:
        model  = MOComponent
        fields = ["id", "product", "product_name", "product_sku",
                  "qty_required", "qty_consumed", "uom", "sequence"]
        read_only_fields = ["id", "qty_consumed"]


class WorkOrderSerializer(serializers.ModelSerializer):
    work_center_name = serializers.CharField(source="work_center.name", read_only=True)
    status_display   = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model  = WorkOrder
        fields = ["id", "work_center", "work_center_name", "name", "sequence",
                  "duration_expected", "duration_actual", "status", "status_display"]
        read_only_fields = ["id"]


class ManufacturingOrderSerializer(serializers.ModelSerializer):
    product_name   = serializers.CharField(source="product.name", read_only=True)
    bom_reference  = serializers.CharField(source="bom.reference", read_only=True, allow_null=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    progress_pct   = serializers.IntegerField(read_only=True)
    components     = MOComponentSerializer(many=True, read_only=True)
    work_orders    = WorkOrderSerializer(many=True, read_only=True)

    class Meta:
        model  = ManufacturingOrder
        fields = [
            "id", "reference", "product", "product_name", "bom", "bom_reference",
            "qty_to_produce", "qty_produced", "progress_pct",
            "status", "status_display", "scheduled_date", "notes",
            "components", "work_orders", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "reference", "qty_produced", "created_at", "updated_at"]


class ManufacturingOrderWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ManufacturingOrder
        fields = ["id", "product", "qty_to_produce", "bom", "scheduled_date", "notes"]
        read_only_fields = ["id"]
