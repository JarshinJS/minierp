from django.db import models


class AuditableMixin(models.Model):
    audit_module = None
    audit_record_type = None

    class Meta:
        abstract = True

    @classmethod
    def get_audit_module(cls):
        return cls.audit_module or cls._meta.app_label

    @classmethod
    def get_audit_record_type(cls):
        return cls.audit_record_type or cls.__name__