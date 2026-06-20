from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .mixins import AuditableMixin
from .services import log_create, log_delete


@receiver(post_save, dispatch_uid="audit_logs_post_save")
def audit_log_create(sender, instance, created, **kwargs):
    if not created:
        return
    if not isinstance(instance, AuditableMixin):
        return
    log_create(None, instance)


@receiver(post_delete, dispatch_uid="audit_logs_post_delete")
def audit_log_delete(sender, instance, **kwargs):
    if not isinstance(instance, AuditableMixin):
        return
    log_delete(None, instance)