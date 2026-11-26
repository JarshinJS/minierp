from rest_framework import serializers

from .models import ProcurementTrigger


class ProcurementTriggerSerializer(serializers.ModelSerializer):
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    document_type_display = serializers.CharField(source="get_document_type_display", read_only=True)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default=None)

    class Meta:
        model = ProcurementTrigger
        fields = [
            "id", "product", "product_sku", "product_name", "quantity_needed", "reference",
            "status", "status_display", "document_type", "document_type_display",
            "document_id", "document_number", "error_message", "processed_at",
            "created_by", "created_by_name", "created_at",
        ]
        read_only_fields = fields
