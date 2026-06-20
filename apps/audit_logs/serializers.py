from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    user_display = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "timestamp",
            "user",
            "user_display",
            "module",
            "record_type",
            "record_id",
            "action",
            "field_changed",
            "old_value",
            "new_value",
        ]

    def get_user_display(self, obj):
        return str(obj.user) if obj.user else ""