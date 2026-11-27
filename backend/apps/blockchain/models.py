"""
models.py for the Blockchain app.

This module contains the models logic for the Blockchain functionality.
"""
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


class MockBlockchainTransaction(models.Model):
    """
    Simulated on-chain transaction used when BLOCKCHAIN_MOCK_MODE is on.

    Stored in the database (not process memory) so every web worker, Celery worker
    and restart sees the same simulated ledger. Offers no tamper resistance: it is
    for development and demos only.
    """
    txn_hash = models.CharField(max_length=66, unique=True)
    input_data = models.CharField(max_length=255, help_text="Data hash submitted in the transaction")
    status = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    BLOCK_OFFSET = 1000

    class Meta:
        ordering = ["id"]

    @property
    def block_number(self):
        return self.BLOCK_OFFSET + self.pk

    def __str__(self):
        return f"mock-tx {self.txn_hash[:12]}… (block {self.block_number})"


class BlockchainWallet(models.Model):
    """
    Per-wallet nonce bookkeeping for live submissions.

    Every Celery worker allocates nonces through this row (locked for the duration
    of allocation + signing), so concurrent workers never sign two transactions
    with the same nonce, even when the RPC node's pending count lags.
    """
    address = models.CharField(max_length=42, help_text="Lower-case 0x address")
    chain_id = models.PositiveBigIntegerField()
    next_nonce = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["address", "chain_id"], name="bc_wallet_address_chain_uniq"),
        ]

    def __str__(self):
        return f"{self.address} (chain {self.chain_id}, next nonce {self.next_nonce})"


class BlockchainSubmission(models.Model):
    """
    Idempotency record for one on-chain submission of a data hash.

    The signed transaction is stored *before* it is broadcast, so a retry after a
    crash, RPC error or receipt timeout re-sends the identical bytes (same nonce,
    same tx hash) instead of creating a second transaction. The raw transaction
    holds a signature, never the private key, and becomes public once broadcast.
    """

    class Status(models.TextChoices):
        SIGNED = "SIGNED", "Signed, not yet broadcast"
        BROADCAST = "BROADCAST", "Broadcast, awaiting receipt"
        CONFIRMED = "CONFIRMED", "Mined successfully"
        FAILED = "FAILED", "Reverted on-chain"
        REPLACED = "REPLACED", "Nonce consumed by another transaction"

    ACTIVE = (Status.SIGNED, Status.BROADCAST, Status.CONFIRMED)

    wallet = models.ForeignKey(BlockchainWallet, on_delete=models.PROTECT, related_name="submissions")
    data_hash = models.CharField(max_length=255, db_index=True)
    nonce = models.PositiveBigIntegerField()
    txn_hash = models.CharField(max_length=66, unique=True)
    raw_transaction = models.TextField(help_text="Signed transaction, 0x hex")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SIGNED, db_index=True)
    block_number = models.PositiveBigIntegerField(null=True, blank=True)
    broadcast_attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["wallet", "nonce"]
        constraints = [
            models.UniqueConstraint(fields=["wallet", "nonce"], name="bc_submission_wallet_nonce_uniq"),
            models.UniqueConstraint(
                fields=["wallet", "data_hash"],
                condition=models.Q(status__in=["SIGNED", "BROADCAST", "CONFIRMED"]),
                name="bc_submission_one_active_per_hash",
            ),
        ]

    def __str__(self):
        return f"{self.txn_hash[:12]}… nonce {self.nonce} [{self.status}]"
