import pytest
from core.exceptions import DomainError, WorkflowError, InsufficientStockError
from core.models import UUIDBaseModel, TimeStampedModel

def test_exceptions():
    with pytest.raises(DomainError) as exc_info:
        raise DomainError("Test domain error")
    assert str(exc_info.value) == "Test domain error"

    with pytest.raises(WorkflowError) as exc_info:
        raise WorkflowError("Test workflow error")
    assert str(exc_info.value) == "Test workflow error"

    with pytest.raises(InsufficientStockError) as exc_info:
        raise InsufficientStockError("Test stock error")
    assert str(exc_info.value) == "Test stock error"

def test_model_abstractions():
    # Verify that the classes are configured as abstract base models
    assert UUIDBaseModel._meta.abstract is True
    assert TimeStampedModel._meta.abstract is True
