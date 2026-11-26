from celery import shared_task

from . import services


@shared_task(bind=True, name="apps.procurement.create_procurement_document")
def create_procurement_document(self, trigger_id):
    return services.create_procurement_document(trigger_id)