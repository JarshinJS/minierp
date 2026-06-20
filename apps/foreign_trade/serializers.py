from rest_framework import serializers
from .models import (
    Country, Currency, Incoterm,
    TradeCustomer, TradeSupplier,
    ExportOrder, ExportOrderLine, ExportInvoice,
    ImportOrder, ImportOrderLine,
    Shipment, TradeDocument,
)


# === Lookups ===

class CountrySerializer(serializers.ModelSerializer):
    class Meta:
        model = Country
        fields = ["id", "name", "code", "region"]


class CurrencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Currency
        fields = ["id", "code", "name", "symbol", "exchange_rate"]


class IncotermSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incoterm
        fields = ["id", "code", "name", "description"]


# === Partners ===

class TradeCustomerSerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)
    country_id = serializers.PrimaryKeyRelatedField(
        queryset=Country.objects.all(), source="country", write_only=True
    )

    class Meta:
        model = TradeCustomer
        fields = ["id", "name", "country", "country_id", "email", "phone", "tax_id", "address", "is_active"]


class TradeSupplierSerializer(serializers.ModelSerializer):
    country = CountrySerializer(read_only=True)
    country_id = serializers.PrimaryKeyRelatedField(
        queryset=Country.objects.all(), source="country", write_only=True
    )

    class Meta:
        model = TradeSupplier
        fields = ["id", "name", "country", "country_id", "email", "phone", "tax_id", "address", "is_active"]


# === Trade Document ===

class TradeDocumentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.get_full_name", read_only=True)

    class Meta:
        model = TradeDocument
        fields = [
            "id", "document_type", "title", "file", "version",
            "verification_status", "uploaded_by", "uploaded_by_name",
            "notes", "created_at"
        ]
        read_only_fields = ["version", "verification_status", "uploaded_by"]


# === Shipments ===

class ShipmentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Shipment
        fields = [
            "id", "shipment_number", "carrier", "tracking_number", "vessel_name",
            "port_of_loading", "port_of_destination", "departure_date", "arrival_date",
            "status", "status_display", "notes", "created_by", "created_by_name", "created_at"
        ]
        read_only_fields = ["shipment_number", "created_by"]


# === Export Orders ===

class ExportOrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExportOrderLine
        fields = ["id", "description", "hs_code", "quantity", "unit_price", "subtotal"]
        read_only_fields = ["subtotal"]


class ExportOrderSerializer(serializers.ModelSerializer):
    customer = TradeCustomerSerializer(read_only=True)
    customer_id = serializers.PrimaryKeyRelatedField(queryset=TradeCustomer.objects.all(), source="customer", write_only=True)
    country = CountrySerializer(read_only=True)
    country_id = serializers.PrimaryKeyRelatedField(queryset=Country.objects.all(), source="country", write_only=True)
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.PrimaryKeyRelatedField(queryset=Currency.objects.all(), source="currency", write_only=True)
    
    lines = ExportOrderLineSerializer(many=True, read_only=True)
    lines_data = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False,
        help_text="List of line items: [{'description': '...', 'quantity': 1, 'unit_price': 100}]"
    )
    
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = ExportOrder
        fields = [
            "id", "order_number", "customer", "customer_id", "country", "country_id",
            "currency", "currency_id", "incoterm", "shipping_method",
            "port_of_loading", "port_of_destination", "container_details",
            "status", "status_display", "notes", "total_amount", "lines", "lines_data",
            "created_at"
        ]
        read_only_fields = ["order_number", "status"]


# === Import Orders ===

class ImportOrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportOrderLine
        fields = ["id", "description", "hs_code", "quantity", "unit_price", "subtotal"]
        read_only_fields = ["subtotal"]


class ImportOrderSerializer(serializers.ModelSerializer):
    supplier = TradeSupplierSerializer(read_only=True)
    supplier_id = serializers.PrimaryKeyRelatedField(queryset=TradeSupplier.objects.all(), source="supplier", write_only=True)
    country = CountrySerializer(read_only=True)
    country_id = serializers.PrimaryKeyRelatedField(queryset=Country.objects.all(), source="country", write_only=True)
    currency = CurrencySerializer(read_only=True)
    currency_id = serializers.PrimaryKeyRelatedField(queryset=Currency.objects.all(), source="currency", write_only=True)
    
    lines = ImportOrderLineSerializer(many=True, read_only=True)
    lines_data = serializers.ListField(
        child=serializers.DictField(), write_only=True, required=False
    )
    
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    customs_status_display = serializers.CharField(source="get_customs_status_display", read_only=True)
    total_amount = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = ImportOrder
        fields = [
            "id", "order_number", "supplier", "supplier_id", "country", "country_id",
            "currency", "currency_id", "container_number", "eta",
            "status", "status_display", "customs_status", "customs_status_display",
            "notes", "total_amount", "lines", "lines_data", "created_at"
        ]
        read_only_fields = ["order_number", "status", "customs_status"]
