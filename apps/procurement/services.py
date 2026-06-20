from decimal import Decimal
from core.exceptions import DomainError
from .models import ProcurementRequest, ProcurementStatus

def trigger_procurement(product, quantity_needed, reference=""):
    """
    Creates a new pending ProcurementRequest for the given product.
    Called when a Sales Order experiences stock shortages during confirmation.
    """
    quantity_needed = Decimal(str(quantity_needed))
    if quantity_needed <= 0:
        raise DomainError("Procurement quantity must be positive.")
        
    request = ProcurementRequest.objects.create(
        product=product,
        quantity_needed=quantity_needed,
        reference=reference,
        status=ProcurementStatus.PENDING
    )
    return request
