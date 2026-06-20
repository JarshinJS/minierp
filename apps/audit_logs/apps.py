from django.apps import AppConfig


class AuditLogsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.audit_logs"

    def ready(self):
        from . import signals  # noqa: F401
