from django.contrib import admin
from .models import BlockchainDocument, BlockchainAuditLog


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
