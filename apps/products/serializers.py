from rest_framework import serializers
from .models import Product, Category

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
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
            "cost_price",
            "selling_price",
            "on_hand_qty",
            "reserved_qty",
            "available_qty",
            "procure_on_demand",
            "procurement_type",
            "default_vendor",
            "default_bom",
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
