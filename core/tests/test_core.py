import pytest
from core.api_views import parse_transcript_fallback
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


def test_fallback_parser_detects_product_creation():
    result = parse_transcript_fallback("create a product called Oak Chair cost 500 selling price 800")

    assert result["action"] == "create_product"
    assert result["data"]["name"] == "Oak Chair"
    assert result["data"]["cost_price"] == 500
    assert result["data"]["selling_price"] == 800


def test_fallback_parser_detects_sales_order_and_stock_change():
    sales_result = parse_transcript_fallback("create a sales order for customer Raj with 5 tables")
    stock_result = parse_transcript_fallback("change stock of Oak Chair by 2")

    assert sales_result["action"] == "create_sales_order"
    assert sales_result["data"]["customer_name"] == "Raj"
    assert sales_result["data"]["lines"][0]["product_name"] == "tables"
    assert sales_result["data"]["lines"][0]["quantity"] == 5

    assert stock_result["action"] == "update_stock"
    assert stock_result["data"]["product_name"] == "Oak Chair"
    assert stock_result["data"]["quantity"] == 2


def test_fallback_parser_handles_make_and_inventory_phrases():
    product_result = parse_transcript_fallback("make a product called Oak Chair cost 500 selling price 800")
    inventory_result = parse_transcript_fallback("update inventory for Oak Chair by 2")

    assert product_result["action"] == "create_product"
    assert inventory_result["action"] == "update_stock"
    assert inventory_result["data"]["product_name"] == "Oak Chair"
    assert inventory_result["data"]["quantity"] == 2
