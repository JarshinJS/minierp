from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any

import ollama
from django.apps import apps
from django.db import transaction
from core.exceptions import DomainError
from apps.products.models import Product
from apps.audit_logs.services import log_event
from apps.audit_logs.models import AuditLogAction
from .models import InventoryLedgerEntry, LedgerEntryType

logger = logging.getLogger(__name__)

DEFAULT_NO_CONTEXT_MESSAGE = "No critical negative stock balances were found."
DEFAULT_USER_INSTRUCTION = (
    "Provide a concise inventory risk summary focused only on critical negative stock balances."
)
DEFAULT_SYSTEM_INSTRUCTIONS = (
    "You are an inventory analytics assistant. Use only the provided context block. "
    "Do not hallucinate product names, invent numbers, infer causes, or assume any data outside the context. "
    "If the context is empty or indicates no issues, say so plainly and do not fabricate details."
)

@transaction.atomic
def post_ledger_entry(product, entry_type, quantity, reference=""):
    """
    Core function to post inventory ledger entries and modify product stock.
    This is the ONLY function allowed to modify Product.on_hand_qty and Product.reserved_qty.
    """
    quantity = Decimal(str(quantity))
    if quantity <= 0:
        raise DomainError("Quantity must be positive.")

    # Select product with lock to prevent race conditions
    product_locked = Product.objects.select_for_update().get(pk=product.id)

    old_on_hand = product_locked.on_hand_qty
    old_reserved = product_locked.reserved_qty

    if entry_type == LedgerEntryType.RECEIPT:
        product_locked.on_hand_qty += quantity
    elif entry_type == LedgerEntryType.ISSUE:
        if product_locked.on_hand_qty < quantity:
            raise DomainError(f"Cannot issue {quantity} stock; only {product_locked.on_hand_qty} on hand for {product_locked.name}.")
        product_locked.on_hand_qty -= quantity
        # Also adjust reserved quantity by the amount issued
        product_locked.reserved_qty = max(Decimal("0.0"), product_locked.reserved_qty - quantity)
    elif entry_type == LedgerEntryType.RESERVATION:
        product_locked.reserved_qty += quantity
    elif entry_type == LedgerEntryType.RELEASE:
        if product_locked.reserved_qty < quantity:
            raise DomainError(f"Cannot release {quantity} stock; only {product_locked.reserved_qty} reserved.")
        product_locked.reserved_qty -= quantity
    else:
        raise DomainError(f"Unknown ledger entry type: {entry_type}")

    product_locked.save()

    # Sync back to memory reference if they are different objects
    product.on_hand_qty = product_locked.on_hand_qty
    product.reserved_qty = product_locked.reserved_qty

    entry = InventoryLedgerEntry.objects.create(
        product=product_locked,
        quantity=quantity,
        entry_type=entry_type,
        reference=reference
    )

    # Log inventory movement as STOCK_ADJUSTED
    if entry_type in [LedgerEntryType.RECEIPT, LedgerEntryType.ISSUE]:
        log_event(
            user=None,
            module="inventory",
            record=product_locked,
            action=AuditLogAction.STOCK_ADJUSTED,
            field="on_hand_qty",
            old=old_on_hand,
            new=product_locked.on_hand_qty
        )
    elif entry_type in [LedgerEntryType.RESERVATION, LedgerEntryType.RELEASE]:
        log_event(
            user=None,
            module="inventory",
            record=product_locked,
            action=AuditLogAction.STOCK_ADJUSTED,
            field="reserved_qty",
            old=old_reserved,
            new=product_locked.reserved_qty
        )

    return entry


@transaction.atomic
def reserve_stock(product, quantity):
    """
    Reserves stock for a sales order. Increments product's reserved quantity.
    """
    post_ledger_entry(product, LedgerEntryType.RESERVATION, quantity, reference="Sales Order Reservation")
    return product


@transaction.atomic
def release_stock(product, quantity):
    """
    Releases reserved stock (e.g. on order cancellation).
    """
    post_ledger_entry(product, LedgerEntryType.RELEASE, quantity, reference="Sales Order Release")
    return product


@transaction.atomic
def issue_stock(product, quantity, reference=""):
    """
    Issues stock (delivery). Subtracts from on_hand_qty, and deallocates from reserved_qty.
    """
    post_ledger_entry(product, LedgerEntryType.ISSUE, quantity, reference=reference)
    return product


@transaction.atomic
def receive_stock(product, quantity, reference=""):
    """
    Receives stock (e.g. purchase receipt or manufacturing input).
    """
    post_ledger_entry(product, LedgerEntryType.RECEIPT, quantity, reference=reference)
    return product


class InventoryRAGService:
    """
    Service class for inventory-aware RAG summaries using a local Ollama model.

    Pipeline:
    1. Retrieval: query negative-stock inventory records.
    2. Augmentation: build a strict prompt with a context block.
    3. Generation: execute the Ollama inference call.
    """

    def __init__(
        self,
        model_name: str = "llama3",
        inventory_model_label: str = "inventory.Inventory",
        stock_field_name: str = "stock",
        client: ollama.Client | None = None,
    ) -> None:
        self.model_name = model_name
        self.inventory_model_label = inventory_model_label
        self.stock_field_name = stock_field_name
        self._client = client or ollama.Client()

    def generate(self, user_instruction: str = DEFAULT_USER_INSTRUCTION) -> str:
        """Run the full retrieval, augmentation, and generation pipeline."""
        context_block = self._retrieve_context()
        messages = self._build_prompt(context_block=context_block, user_instruction=user_instruction)
        return self.execute_inference(messages)

    def _resolve_inventory_model(self) -> tuple[type[Any], str]:
        """
        Resolve the primary inventory model contract, falling back to Product for
        this workspace layout where stock is tracked on Product.on_hand_qty.
        """
        try:
            app_label, model_name = self.inventory_model_label.split(".", 1)
            inventory_model = apps.get_model(app_label, model_name)
            if inventory_model is not None and any(
                field.name == self.stock_field_name for field in inventory_model._meta.get_fields()
            ):
                return inventory_model, self.stock_field_name
        except (LookupError, ValueError):
            pass

        return Product, "on_hand_qty"

    def _retrieve_context(self) -> str:
        """Retrieve and format only critical negative stock rows."""
        inventory_model, stock_field_name = self._resolve_inventory_model()
        queryset = inventory_model.objects.filter(**{f"{stock_field_name}__lt": 0}).order_by(stock_field_name)

        if not queryset.exists():
            return DEFAULT_NO_CONTEXT_MESSAGE

        lines = ["=== NEGATIVE STOCK CONTEXT START ==="]
        for item in queryset:
            item_name = getattr(item, "name", None) or getattr(item, "sku", None) or str(item)
            stock_value = getattr(item, stock_field_name)
            lines.append(f"Item: {item_name} | Stock: {stock_value}")
        lines.append("=== NEGATIVE STOCK CONTEXT END ===")
        return "\n".join(lines)

    def _build_prompt(self, context_block: str, user_instruction: str) -> list[dict[str, str]]:
        """Build a deterministic prompt that constrains the model to the supplied context."""
        return [
            {
                "role": "system",
                "content": DEFAULT_SYSTEM_INSTRUCTIONS,
            },
            {
                "role": "user",
                "content": (
                    f"{user_instruction}\n\n"
                    "CONTEXT BLOCK START\n"
                    f"{context_block}\n"
                    "CONTEXT BLOCK END\n\n"
                    "Use only the context block above. Do not add unsupported names, numbers, or assumptions."
                ),
            },
        ]

    def execute_inference(self, messages: list[dict[str, str]]) -> str:
        """Execute Ollama inference with strict deterministic options and graceful failure handling."""
        try:
            response = self._client.chat(
                model=self.model_name,
                messages=messages,
                options={
                    "temperature": 0.3,
                    "top_p": 0.2,
                    "top_k": 20,
                },
            )
            return self._extract_content(response)
        except TimeoutError:
            logger.exception("Ollama inference timed out for model %s.", self.model_name)
            return "Ollama inference timed out. The inventory context was prepared, but the local model did not respond in time."
        except ConnectionError:
            logger.exception("Ollama server is unavailable for model %s.", self.model_name)
            return "Ollama server is unavailable. Start the local Ollama service and try again."
        except OSError:
            logger.exception("Operating-system error while calling Ollama for model %s.", self.model_name)
            return "Unable to reach the local Ollama service due to a system-level error."
        except Exception:
            logger.exception("Unexpected Ollama inference failure for model %s.", self.model_name)
            return "Unable to complete the inventory RAG request right now. Please retry after the local Ollama service is healthy."

    def _extract_content(self, response: Any) -> str:
        """Normalize Ollama's response object into plain text."""
        if hasattr(response, "message") and hasattr(response.message, "content"):
            return str(response.message.content)

        if isinstance(response, dict):
            message = response.get("message", {})
            if isinstance(message, dict):
                return str(message.get("content", ""))

        return str(response)
