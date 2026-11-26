from decimal import Decimal

from rest_framework import serializers

from .validators import validate_trade_document_file
from .models import (
    Country, Currency, Incoterm,
    TradeCustomer, TradeSupplier,
    ExportOrder, ExportOrderLine, ExportInvoice,
    ImportOrder, ImportOrderLine,
    Shipment, TradeDocument, DocumentType,
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
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True)
    order_type = serializers.SerializerMethodField()
    order_id = serializers.UUIDField(source="object_id", read_only=True)

    class Meta:
        model = TradeDocument
        fields = [
            "id", "document_type", "title", "file", "version",
            "verification_status", "uploaded_by", "uploaded_by_name",
            "order_type", "order_id", "notes", "created_at"
        ]
        read_only_fields = ["version", "verification_status", "uploaded_by"]

    def get_order_type(self, doc) -> str:
        return {"exportorder": "export", "importorder": "import"}.get(doc.content_type.model, doc.content_type.model)


class TradeDocumentUploadSerializer(serializers.Serializer):
    """multipart/form-data upload of a new document version for an order."""
    order_type = serializers.ChoiceField(choices=["export", "import"])
    order_id = serializers.UUIDField()
    document_type = serializers.ChoiceField(choices=DocumentType.choices)
    title = serializers.CharField(max_length=255)
    file = serializers.FileField(validators=[validate_trade_document_file])
    notes = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        model = ExportOrder if attrs["order_type"] == "export" else ImportOrder
        try:
            attrs["order"] = model.objects.get(pk=attrs["order_id"])
        except model.DoesNotExist:
            raise serializers.ValidationError({"order_id": "Order not found."})
        return attrs


# === Shipments ===

class ShipmentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Shipment
        fields = [
            "id", "shipment_number", "carrier", "tracking_number", "vessel_name",
            "port_of_loading", "port_of_destination", "departure_date", "arrival_date",
            "status", "status_display", "notes", "created_by", "created_by_name", "created_at"
        ]
        read_only_fields = ["shipment_number", "created_by"]


# === Order line input (write) ===

class OrderLineInputSerializer(serializers.Serializer):
    description = serializers.CharField(max_length=500)
    hs_code = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    unit_price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"))


# === Export Orders ===

class ExportOrderLineSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

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
    lines_data = OrderLineInputSerializer(
        many=True, write_only=True, required=False,
        help_text="Line items (required on create; ignored on update).",
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
    subtotal = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

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
    lines_data = OrderLineInputSerializer(
        many=True, write_only=True, required=False,
        help_text="Line items (required on create; ignored on update).",
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


# === Invoices & workflow inputs ===

class ExportInvoiceSerializer(serializers.ModelSerializer):
    currency_code = serializers.CharField(source="currency.code", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ExportInvoice
        fields = [
            "id", "invoice_number", "export_order", "amount", "currency", "currency_code",
            "status", "status_display", "due_date", "notes", "created_at",
        ]
        read_only_fields = fields


class ExportInvoiceCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"), required=False,
                                      help_text="Defaults to the order total.")
    due_date = serializers.DateField(required=False, allow_null=True, default=None)
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class ShipmentInputSerializer(serializers.Serializer):
    carrier = serializers.CharField(required=False, allow_blank=True, default="")
    tracking_number = serializers.CharField(required=False, allow_blank=True, default="")
    vessel_name = serializers.CharField(required=False, allow_blank=True, default="")
