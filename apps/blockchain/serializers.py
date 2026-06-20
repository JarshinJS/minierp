from rest_framework import serializers
from .models import BlockchainDocument, BlockchainAuditLog


class BlockchainDocumentSerializer(serializers.ModelSerializer):
    document_title = serializers.CharField(source="document.title", read_only=True)
    document_type = serializers.CharField(source="document.document_type", read_only=True)

    class Meta:
        model = BlockchainDocument
        fields = [
            "id", "document", "document_title", "document_type",
            "document_hash", "blockchain_txn", "network", "block_number",
            "verified", "created_at"
        ]
        read_only_fields = fields


class BlockchainAuditLogSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source="created_by.get_full_name", read_only=True, default="System")
    event_type_display = serializers.CharField(source="get_event_type_display", read_only=True)

    class Meta:
        model = BlockchainAuditLog
        fields = [
            "id", "event_type", "event_type_display", "reference_id", "reference_model",
            "data_hash", "blockchain_txn", "network", "block_number",
            "created_by", "created_by_name", "metadata", "created_at"
        ]
        read_only_fields = fields
