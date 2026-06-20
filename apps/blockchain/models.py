from django.conf import settings
from django.db import models

from core.models import UUIDBaseModel, TimeStampedModel


class BlockchainDocument(UUIDBaseModel, TimeStampedModel):
    """Links an ERP TradeDocument to a blockchain transaction for tamper-proof verification."""
    document = models.ForeignKey(
        "foreign_trade.TradeDocument",
        on_delete=models.CASCADE,
        related_name="blockchain_records",
    )
    document_hash = models.CharField(max_length=255, db_index=True, help_text="SHA-256 hash of the document file")
    blockchain_txn = models.CharField(max_length=255, db_index=True, help_text="Blockchain transaction hash")
    network = models.CharField(max_length=100, default="polygon-amoy")
    block_number = models.PositiveBigIntegerField(null=True, blank=True)
    verified = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["document_hash"]),
            models.Index(fields=["blockchain_txn"]),
        ]

    def __str__(self):
        status = "✓ Verified" if self.verified else "⏳ Pending"
        return f"BC:{self.document.title} [{status}]"


class BlockchainAuditLog(UUIDBaseModel, TimeStampedModel):
    """Immutable blockchain-backed audit trail for critical business events."""

    class EventType(models.TextChoices):
        ORDER_CREATED = "ORDER_CREATED", "Order Created"
        ORDER_CONFIRMED = "ORDER_CONFIRMED", "Order Confirmed"
        ORDER_APPROVED = "ORDER_APPROVED", "Order Approved"
        INVOICE_GENERATED = "INVOICE_GENERATED", "Invoice Generated"
        SHIPMENT_DISPATCHED = "SHIPMENT_DISPATCHED", "Shipment Dispatched"
        SHIPMENT_DELIVERED = "SHIPMENT_DELIVERED", "Shipment Delivered"
        CUSTOMS_CLEARED = "CUSTOMS_CLEARED", "Customs Cleared"
        PAYMENT_RECEIVED = "PAYMENT_RECEIVED", "Payment Received"
        DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED", "Document Uploaded"
        DOCUMENT_VERIFIED = "DOCUMENT_VERIFIED", "Document Verified"
        STATUS_CHANGED = "STATUS_CHANGED", "Status Changed"

    event_type = models.CharField(max_length=100, choices=EventType.choices, db_index=True)
    reference_id = models.CharField(max_length=100, db_index=True, help_text="UUID or order number of the related record")
    reference_model = models.CharField(max_length=100, blank=True, help_text="Model name, e.g. ExportOrder")
    data_hash = models.CharField(max_length=255, help_text="SHA-256 hash of the event data")
    blockchain_txn = models.CharField(max_length=255, db_index=True, help_text="Blockchain transaction hash")
    network = models.CharField(max_length=100, default="polygon-amoy")
    block_number = models.PositiveBigIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="blockchain_audit_logs",
    )
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional event context")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "created_at"]),
            models.Index(fields=["reference_id"]),
        ]

    def __str__(self):
        return f"[{self.get_event_type_display()}] {self.reference_id} @ {self.created_at:%Y-%m-%d %H:%M}"
