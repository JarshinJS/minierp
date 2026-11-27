"""
admin.py for the Blockchain app.

This module contains the admin logic for the Blockchain functionality.
"""
from django.contrib import admin
from .models import BlockchainAuditLog, BlockchainDocument, BlockchainSubmission, BlockchainWallet


@admin.register(BlockchainDocument)
class BlockchainDocumentAdmin(admin.ModelAdmin):
    list_display = ("document", "document_hash", "blockchain_txn", "network", "verified", "created_at")
    search_fields = ("document_hash", "blockchain_txn")
    list_filter = ("verified", "network")
    readonly_fields = ("document_hash", "blockchain_txn", "network", "block_number", "verified")


@admin.register(BlockchainAuditLog)
class BlockchainAuditLogAdmin(admin.ModelAdmin):
    list_display = ("event_type", "reference_id", "reference_model", "blockchain_txn", "created_by", "created_at")
    search_fields = ("reference_id", "blockchain_txn", "data_hash")
    list_filter = ("event_type", "network")
    readonly_fields = ("data_hash", "blockchain_txn", "network", "block_number")


class _ReadOnlyAdmin(admin.ModelAdmin):
    """Nonce/submission bookkeeping is written only by the service; editing it by hand
    can cause nonce collisions or duplicate anchoring."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BlockchainWallet)
class BlockchainWalletAdmin(_ReadOnlyAdmin):
    list_display = ("address", "chain_id", "next_nonce", "updated_at")


@admin.register(BlockchainSubmission)
class BlockchainSubmissionAdmin(_ReadOnlyAdmin):
    list_display = ("txn_hash", "nonce", "status", "block_number", "broadcast_attempts", "last_error", "updated_at")
    list_filter = ("status", "wallet")
    search_fields = ("txn_hash", "data_hash")
    exclude = ("raw_transaction",)
