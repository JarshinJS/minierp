class DomainError(Exception):
    """
    Base exception for all domain logic violations.
    All custom domain exceptions should inherit from this.
    """
    def __init__(self, message="A domain error occurred.", *args, **kwargs):
        self.message = message
        super().__init__(message, *args, **kwargs)


class WorkflowError(DomainError):
    """
    Exception raised when a business workflow constraint is violated.
    For example, attempting to approve an already approved invoice.
    """
    def __init__(self, message="Invalid workflow state transition.", *args, **kwargs):
        super().__init__(message, *args, **kwargs)


class InsufficientStockError(DomainError):
    """
    Exception raised when an operation fails due to insufficient inventory stock.
    """
    def __init__(self, message="Insufficient inventory stock to complete the operation.", *args, **kwargs):
        super().__init__(message, *args, **kwargs)
