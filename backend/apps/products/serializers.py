from rest_framework import serializers
from .models import Product, Category

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    unit_of_measure_display = serializers.CharField(source="get_unit_of_measure_display", read_only=True)
    procurement_type_display = serializers.CharField(source="get_procurement_type_display", read_only=True)
    default_vendor_name = serializers.CharField(source="default_vendor.name", read_only=True, default=None)
    default_bom_name = serializers.CharField(source="default_bom.name", read_only=True, default=None)
    available_qty = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "category",
            "category_name",
            "unit_of_measure",
            "unit_of_measure_display",
            "cost_price",
            "selling_price",
            "on_hand_qty",
            "reserved_qty",
            "available_qty",
            "procure_on_demand",
            "procurement_type",
            "procurement_type_display",
            "default_vendor",
            "default_vendor_name",
            "default_bom",
            "default_bom_name",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "on_hand_qty",
            "reserved_qty",
            "available_qty",
            "created_at",
            "updated_at",
        ]
