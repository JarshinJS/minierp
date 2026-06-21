"""
models.py for the Foreign_trade app.

This module contains the models logic for the Foreign_trade functionality.
"""
import uuid

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from core.models import UUIDBaseModel, TimeStampedModel
from apps.audit_logs.mixins import AuditableMixin


# ---------------------------------------------------------------------------
# Lookup / Reference Tables
# ---------------------------------------------------------------------------

class Country(UUIDBaseModel, TimeStampedModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=3, unique=True, db_index=True, help_text="ISO 3166-1 alpha-2/3")
    region = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name_plural = "Countries"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Currency(UUIDBaseModel, TimeStampedModel):
    code = models.CharField(max_length=3, unique=True, db_index=True, help_text="ISO 4217")
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10, blank=True)
    exchange_rate = models.DecimalField(
        max_digits=12, decimal_places=6, default=1,
        help_text="Rate relative to base currency (e.g. 1 USD = X)"
    )

    class Meta:
        verbose_name_plural = "Currencies"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} – {self.name}"


class Incoterm(UUIDBaseModel, TimeStampedModel):
    code = models.CharField(max_length=10, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} – {self.name}"


# ---------------------------------------------------------------------------
# Trade Partners
# ---------------------------------------------------------------------------

class TradeCustomer(AuditableMixin, UUIDBaseModel, TimeStampedModel):
    audit_module = "foreign_trade"
    audit_record_type = "TradeCustomer"

    name = models.CharField(max_length=255, db_index=True)
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="customers")
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    tax_id = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class TradeSupplier(AuditableMixin, UUIDBaseModel, TimeStampedModel):
    audit_module = "foreign_trade"
    audit_record_type = "TradeSupplier"

    name = models.CharField(max_length=255, db_index=True)
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="suppliers")
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    tax_id = models.CharField(max_length=100, blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


# ---------------------------------------------------------------------------
# Status Enums
# ---------------------------------------------------------------------------

class ExportOrderStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    QUOTATION = "QUOTATION", "Quotation"
    CONFIRMED = "CONFIRMED", "Confirmed"
    SHIPPED = "SHIPPED", "Shipped"
    DELIVERED = "DELIVERED", "Delivered"
    CANCELLED = "CANCELLED", "Cancelled"


class ImportOrderStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    CONFIRMED = "CONFIRMED", "Confirmed"
    IN_TRANSIT = "IN_TRANSIT", "In Transit"
    CUSTOMS = "CUSTOMS", "Customs"
    RECEIVED = "RECEIVED", "Received"
    CANCELLED = "CANCELLED", "Cancelled"


class ShipmentStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    IN_TRANSIT = "IN_TRANSIT", "In Transit"
    AT_PORT = "AT_PORT", "At Port"
    CUSTOMS = "CUSTOMS", "Customs"
    DELIVERED = "DELIVERED", "Delivered"


class CustomsStatus(models.TextChoices):
    NOT_STARTED = "NOT_STARTED", "Not Started"
    DOCUMENTS_SUBMITTED = "DOCUMENTS_SUBMITTED", "Documents Submitted"
    UNDER_REVIEW = "UNDER_REVIEW", "Under Review"
    CLEARED = "CLEARED", "Cleared"
    HELD = "HELD", "Held"


class ShippingMethod(models.TextChoices):
    SEA = "SEA", "Sea Freight"
    AIR = "AIR", "Air Freight"
    ROAD = "ROAD", "Road Transport"
    RAIL = "RAIL", "Rail Freight"
    MULTIMODAL = "MULTIMODAL", "Multimodal"


class DocumentType(models.TextChoices):
    COMMERCIAL_INVOICE = "COMMERCIAL_INVOICE", "Commercial Invoice"
    PACKING_LIST = "PACKING_LIST", "Packing List"
    BILL_OF_LADING = "BILL_OF_LADING", "Bill of Lading"
    CERTIFICATE_OF_ORIGIN = "CERTIFICATE_OF_ORIGIN", "Certificate of Origin"
    INSURANCE_CERTIFICATE = "INSURANCE_CERTIFICATE", "Insurance Certificate"
    CUSTOMS_DECLARATION = "CUSTOMS_DECLARATION", "Customs Declaration"
    OTHER = "OTHER", "Other"


class DocumentVerificationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    VERIFIED = "VERIFIED", "Verified"
    TAMPERED = "TAMPERED", "Tampered"
    UNVERIFIED = "UNVERIFIED", "Unverified"


class InvoiceStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SENT = "SENT", "Sent"
    PAID = "PAID", "Paid"
    OVERDUE = "OVERDUE", "Overdue"
    CANCELLED = "CANCELLED", "Cancelled"


# ---------------------------------------------------------------------------
# Export Orders
# ---------------------------------------------------------------------------

class ExportOrder(AuditableMixin, UUIDBaseModel, TimeStampedModel):
    audit_module = "foreign_trade"
    audit_record_type = "ExportOrder"

    order_number = models.CharField(max_length=100, unique=True, db_index=True)
    customer = models.ForeignKey(TradeCustomer, on_delete=models.PROTECT, related_name="export_orders")
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="export_orders")
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="export_orders")
    incoterm = models.ForeignKey(Incoterm, on_delete=models.SET_NULL, null=True, blank=True, related_name="export_orders")
    shipping_method = models.CharField(max_length=20, choices=ShippingMethod.choices, default=ShippingMethod.SEA)
    port_of_loading = models.CharField(max_length=255, blank=True)
    port_of_destination = models.CharField(max_length=255, blank=True)
    container_details = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=ExportOrderStatus.choices, default=ExportOrderStatus.DRAFT, db_index=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="export_orders")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.order_number} – {self.customer.name}"

    @property
    def total_amount(self):
        return sum(line.subtotal for line in self.lines.all())


class ExportOrderLine(UUIDBaseModel, TimeStampedModel):
    export_order = models.ForeignKey(ExportOrder, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=500)
    hs_code = models.CharField(max_length=20, blank=True, help_text="Harmonized System code")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.description} | {self.quantity} @ {self.unit_price}"

    @property
    def subtotal(self):
        return self.quantity * self.unit_price


# ---------------------------------------------------------------------------
# Export Invoices
# ---------------------------------------------------------------------------

class ExportInvoice(AuditableMixin, UUIDBaseModel, TimeStampedModel):
    audit_module = "foreign_trade"
    audit_record_type = "ExportInvoice"

    invoice_number = models.CharField(max_length=100, unique=True, db_index=True)
    export_order = models.ForeignKey(ExportOrder, on_delete=models.CASCADE, related_name="invoices")
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="export_invoices")
    status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT)
    due_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.invoice_number} – {self.amount} {self.currency.code}"


# ---------------------------------------------------------------------------
# Import Orders
# ---------------------------------------------------------------------------

class ImportOrder(AuditableMixin, UUIDBaseModel, TimeStampedModel):
    audit_module = "foreign_trade"
    audit_record_type = "ImportOrder"

    order_number = models.CharField(max_length=100, unique=True, db_index=True)
    supplier = models.ForeignKey(TradeSupplier, on_delete=models.PROTECT, related_name="import_orders")
    country = models.ForeignKey(Country, on_delete=models.PROTECT, related_name="import_orders")
    currency = models.ForeignKey(Currency, on_delete=models.PROTECT, related_name="import_orders")
    container_number = models.CharField(max_length=100, blank=True)
    eta = models.DateField(null=True, blank=True, help_text="Estimated Time of Arrival")
    customs_status = models.CharField(max_length=30, choices=CustomsStatus.choices, default=CustomsStatus.NOT_STARTED, db_index=True)
    status = models.CharField(max_length=30, choices=ImportOrderStatus.choices, default=ImportOrderStatus.DRAFT, db_index=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="import_orders")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.order_number} – {self.supplier.name}"

    @property
    def total_amount(self):
        return sum(line.subtotal for line in self.lines.all())


class ImportOrderLine(UUIDBaseModel, TimeStampedModel):
    import_order = models.ForeignKey(ImportOrder, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=500)
    hs_code = models.CharField(max_length=20, blank=True, help_text="Harmonized System code")
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.description} | {self.quantity} @ {self.unit_price}"

    @property
    def subtotal(self):
        return self.quantity * self.unit_price


# ---------------------------------------------------------------------------
# Shipments
# ---------------------------------------------------------------------------

class Shipment(AuditableMixin, UUIDBaseModel, TimeStampedModel):
    audit_module = "foreign_trade"
    audit_record_type = "Shipment"

    shipment_number = models.CharField(max_length=100, unique=True, db_index=True)
    # Generic relation to either ExportOrder or ImportOrder
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    related_order = GenericForeignKey("content_type", "object_id")

    carrier = models.CharField(max_length=255, blank=True)
    tracking_number = models.CharField(max_length=255, blank=True)
    vessel_name = models.CharField(max_length=255, blank=True)
    port_of_loading = models.CharField(max_length=255, blank=True)
    port_of_destination = models.CharField(max_length=255, blank=True)
    departure_date = models.DateField(null=True, blank=True)
    arrival_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=ShipmentStatus.choices, default=ShipmentStatus.PENDING, db_index=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="shipments")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.shipment_number} ({self.get_status_display()})"


# ---------------------------------------------------------------------------
# Trade Documents
# ---------------------------------------------------------------------------

def trade_document_upload_path(instance, filename):
    return f"trade_documents/{instance.document_type}/{filename}"


class TradeDocument(AuditableMixin, UUIDBaseModel, TimeStampedModel):
    audit_module = "foreign_trade"
    audit_record_type = "TradeDocument"

    document_type = models.CharField(max_length=30, choices=DocumentType.choices, db_index=True)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to=trade_document_upload_path)
    version = models.PositiveIntegerField(default=1)

    # Generic relation to either ExportOrder or ImportOrder
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.UUIDField()
    related_order = GenericForeignKey("content_type", "object_id")

    verification_status = models.CharField(
        max_length=20,
        choices=DocumentVerificationStatus.choices,
        default=DocumentVerificationStatus.PENDING,
        db_index=True,
    )
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="trade_documents")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "object_id", "document_type"]),
        ]

    def __str__(self):
        return f"{self.title} v{self.version} ({self.get_document_type_display()})"
