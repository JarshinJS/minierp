import json
import logging
import uuid
import requests
from decimal import Decimal, InvalidOperation

from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from apps.products.models import Product, Category
from apps.sales.models import SalesOrder, SalesOrderLine, SalesOrderStatus
from apps.purchase.models import PurchaseOrder, PurchaseOrderLine, PurchaseOrderStatus, Vendor
from apps.inventory.services import receive_stock, issue_stock

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.1"

# ──────────────────────────────────────────────
# Prompt template that tells the LLM about the ERP
# ──────────────────────────────────────────────
SYSTEM_PROMPT = """You are an AI assistant for the Shiv Furniture Works ERP system.

Your job is to understand what the user wants to do and return a structured JSON response.

AVAILABLE ACTIONS:
1. "create_product"       — Add a new product to the catalog
2. "create_sales_order"   — Create a new sales order for a customer
3. "create_purchase_order" — Create a new purchase order for a vendor
4. "lookup_product"       — Search for a product by name
5. "lookup_sales_order"   — Search for a sales order by order number or customer name
6. "lookup_purchase_order" — Search for a purchase order by order number or vendor
7. "general_query"        — Answer a general question about the ERP
8. "update_stock"         — Increase or decrease stock levels of a product

RESPONSE FORMAT (return ONLY this JSON, nothing else):
{
  "action": "<one of the action names above>",
  "confidence": <0.0 to 1.0>,
  "reply": "<A short human-friendly message describing what you understood>",
  "data": { ... action-specific data ... }
}

DATA SCHEMAS PER ACTION:

create_product:
{
  "name": "string (required)",
  "sku": "string (auto-generate if not given, format: PROD-XXXX)",
  "category": "string (default: 'General')",
  "cost_price": number (required),
  "selling_price": number (required),
  "unit_of_measure": "PCS | KG | M | BOX (default: PCS)"
}

create_sales_order:
{
  "customer_name": "string (required)",
  "customer_phone": "string (optional)",
  "customer_email": "string (optional)",
  "notes": "string (optional)",
  "lines": [
    {"product_name": "string", "quantity": number, "unit_price": number}
  ]
}

create_purchase_order:
{
  "vendor_name": "string (required)",
  "notes": "string (optional)",
  "lines": [
    {"product_name": "string", "quantity": number, "unit_price": number}
  ]
}

lookup_product:
{ "search_term": "string" }

lookup_sales_order:
{ "search_term": "string" }

lookup_purchase_order:
{ "search_term": "string" }

general_query:
{ "question": "string" }

update_stock:
{
  "product_name": "string (required)",
  "quantity": number (required, absolute value),
  "direction": "increase | decrease (required)"
}

RULES:
- Always pick the BEST matching action.
- If the user mentions a customer, it's likely a sales order.
- If the user mentions a vendor or supplier, it's likely a purchase order.
- If the user says "add product" or "new item", it's create_product.
- Extract ALL relevant data from the sentence.
- For prices, quantities, names — extract exactly what the user said.
- Extract as much information as possible from the user's input.
- Be resilient to speech-to-text typos. If a word sounds like a furniture material (e.g., "coke" instead of "oak", "teak", "plywood", "pine"), assume the furniture material.
- If no explicit intent is matched, default to 'general_query' with low confidence.
"""


def call_ollama(user_message):
    """Call Ollama and return parsed JSON."""
    prompt = f"{SYSTEM_PROMPT}\n\nUSER INPUT: {user_message}"

    response = requests.post(
        f"{OLLAMA_URL}/api/generate",
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.0,
                "num_predict": 256,
                "num_ctx": 2048,
            }
        },
        timeout=60,
    )
    response.raise_for_status()
    raw = response.json().get("response", "").strip()

    # Strip markdown fences
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    raw = raw.strip()

    return json.loads(raw)


def _gen_order_number(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _find_product(name):
    """Fuzzy-match a product by name (case-insensitive contains)."""
    return Product.objects.filter(name__icontains=name, is_active=True).first()


def _find_vendor(name):
    return Vendor.objects.filter(name__icontains=name).first()


def _safe_decimal(value, default="0.00"):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


# ──────────────────────────────────────────────
#  Action handlers
# ──────────────────────────────────────────────

def handle_create_product(data, user):
    name = data.get("name", "").strip()
    if not name:
        return {"success": False, "message": "Product name is required."}

    sku = data.get("sku") or f"PROD-{uuid.uuid4().hex[:6].upper()}"
    cat_name = data.get("category", "General")
    category, _ = Category.objects.get_or_create(name=cat_name)

    cost = _safe_decimal(data.get("cost_price", 0))
    sell = _safe_decimal(data.get("selling_price", 0))
    uom = data.get("unit_of_measure", "PCS")

    if Product.objects.filter(sku=sku).exists():
        return {"success": False, "message": f"Product with SKU '{sku}' already exists."}

    product = Product.objects.create(
        name=name, sku=sku, category=category,
        cost_price=cost, selling_price=sell,
        unit_of_measure=uom, is_active=True,
    )
    return {
        "success": True,
        "message": f"✅ Product '{product.name}' created (SKU: {product.sku}, Cost: ₹{cost}, Sell: ₹{sell}).",
        "record_id": str(product.id),
    }


def handle_create_sales_order(data, user):
    customer = data.get("customer_name", "").strip()
    if not customer:
        return {"success": False, "message": "Customer name is required."}

    lines_data = data.get("lines", [])
    with transaction.atomic():
        order = SalesOrder.objects.create(
            order_number=_gen_order_number("SO"),
            customer_name=customer,
            customer_phone=data.get("customer_phone", ""),
            customer_email=data.get("customer_email", ""),
            notes=data.get("notes", ""),
            created_by=user,
            status=SalesOrderStatus.DRAFT,
        )
        line_msgs = []
        for item in lines_data:
            product = _find_product(item.get("product_name", ""))
            if not product:
                line_msgs.append(f"⚠ Product '{item.get('product_name')}' not found, skipped.")
                continue
            qty = _safe_decimal(item.get("quantity", 1))
            price = _safe_decimal(item.get("unit_price")) or product.selling_price
            SalesOrderLine.objects.create(
                order=order, product=product,
                quantity=qty, unit_price=price,
            )
            line_msgs.append(f"  • {product.name} × {qty} @ ₹{price}")

    summary = "\n".join(line_msgs) if line_msgs else "  (no line items)"
    return {
        "success": True,
        "message": f"✅ Sales Order {order.order_number} created for {customer}.\n{summary}",
        "record_id": str(order.id),
    }


def handle_create_purchase_order(data, user):
    vendor_name = data.get("vendor_name", "").strip()
    if not vendor_name:
        return {"success": False, "message": "Vendor name is required."}

    vendor = _find_vendor(vendor_name)
    if not vendor:
        return {"success": False, "message": f"Vendor '{vendor_name}' not found. Please create the vendor first."}

    lines_data = data.get("lines", [])
    with transaction.atomic():
        order = PurchaseOrder.objects.create(
            order_number=_gen_order_number("PO"),
            vendor=vendor,
            notes=data.get("notes", ""),
            created_by=user,
            status=PurchaseOrderStatus.DRAFT,
        )
        line_msgs = []
        for item in lines_data:
            product = _find_product(item.get("product_name", ""))
            if not product:
                line_msgs.append(f"⚠ Product '{item.get('product_name')}' not found, skipped.")
                continue
            qty = _safe_decimal(item.get("quantity", 1))
            price = _safe_decimal(item.get("unit_price")) or product.cost_price
            PurchaseOrderLine.objects.create(
                purchase_order=order, product=product,
                quantity=qty, unit_price=price,
            )
            line_msgs.append(f"  • {product.name} × {qty} @ ₹{price}")

    summary = "\n".join(line_msgs) if line_msgs else "  (no line items)"
    return {
        "success": True,
        "message": f"✅ Purchase Order {order.order_number} created for {vendor.name}.\n{summary}",
        "record_id": str(order.id),
    }


def handle_lookup_product(data, user):
    term = data.get("search_term", "")
    products = Product.objects.filter(name__icontains=term, is_active=True)[:5]
    if not products:
        return {"success": True, "message": f"No products found matching '{term}'."}
    lines = [f"  • {p.name} (SKU: {p.sku}) — Cost: ₹{p.cost_price}, Sell: ₹{p.selling_price}, Stock: {p.available_qty}" for p in products]
    return {"success": True, "message": f"Found {len(lines)} product(s):\n" + "\n".join(lines)}


def handle_lookup_sales_order(data, user):
    term = data.get("search_term", "")
    orders = SalesOrder.objects.filter(
        models_Q_or(order_number__icontains=term, customer_name__icontains=term)
    )[:5]
    if not orders:
        return {"success": True, "message": f"No sales orders found matching '{term}'."}
    lines = [f"  • {o.order_number} — {o.customer_name} — {o.status} — ₹{o.total_amount}" for o in orders]
    return {"success": True, "message": f"Found {len(lines)} order(s):\n" + "\n".join(lines)}


def handle_lookup_purchase_order(data, user):
    term = data.get("search_term", "")
    orders = PurchaseOrder.objects.filter(
        models_Q_or(order_number__icontains=term, vendor__name__icontains=term)
    )[:5]
    if not orders:
        return {"success": True, "message": f"No purchase orders found matching '{term}'."}
    lines = [f"  • {o.order_number} — {o.vendor.name} — {o.status} — ₹{o.total_amount}" for o in orders]
    return {"success": True, "message": f"Found {len(lines)} order(s):\n" + "\n".join(lines)}


def models_Q_or(**kwargs):
    """Build a Q object that ORs all conditions."""
    from django.db.models import Q
    q = Q()
    for k, v in kwargs.items():
        q |= Q(**{k: v})
    return q


def handle_update_stock(data, user):
    product_name = data.get("product_name", "").strip()
    quantity = _safe_decimal(data.get("quantity", 0))
    direction = data.get("direction", "increase").lower()

    if not product_name or quantity <= 0:
        return {"success": False, "message": "Product name and positive quantity are required."}

    product = _find_product(product_name)
    if not product:
        return {"success": False, "message": f"Could not find a product matching '{product_name}'."}

    try:
        if direction == "increase":
            receive_stock(product, quantity, reference="Voice Update")
            msg = f"Increased stock of {product.name} by {quantity}. New stock: {product.on_hand_qty}"
        else:
            issue_stock(product, quantity, reference="Voice Update")
            msg = f"Decreased stock of {product.name} by {quantity}. New stock: {product.on_hand_qty}"
    except Exception as e:
        return {"success": False, "message": str(e)}

    return {
        "success": True,
        "message": msg,
        "product_id": product.id
    }


ACTION_HANDLERS = {
    "create_product": handle_create_product,
    "create_sales_order": handle_create_sales_order,
    "create_purchase_order": handle_create_purchase_order,
    "lookup_product": handle_lookup_product,
    "lookup_sales_order": handle_lookup_sales_order,
    "lookup_purchase_order": handle_lookup_purchase_order,
    "update_stock": handle_update_stock,
}


# ──────────────────────────────────────────────
#  DRF Views
# ──────────────────────────────────────────────

class VoiceAssistantAPIView(APIView):
    """
    Full end-to-end voice assistant:
    1. Receives transcript
    2. Calls Ollama to determine intent + extract data
    3. Executes the action (creates DB records, runs lookups)
    4. Returns a human-friendly response
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        transcript = request.data.get("transcript", "").strip()
        if not transcript:
            return Response({"error": "No transcript provided."}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Check Ollama
        try:
            requests.get(f"{OLLAMA_URL}/api/tags", timeout=2).raise_for_status()
        except requests.exceptions.RequestException:
            return Response({
                "reply": "⚠ Ollama is not running. Please start it with `ollama serve`.",
                "action": "error",
                "success": False,
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        # 2. Call LLM
        try:
            llm_result = call_ollama(transcript)
        except requests.exceptions.Timeout:
            return Response({
                "reply": "⏳ The AI took too long. Please try a shorter sentence.",
                "action": "error",
                "success": False,
            }, status=status.HTTP_504_GATEWAY_TIMEOUT)
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            logger.error(f"Ollama error: {e}")
            return Response({
                "reply": "❌ Could not understand the response from the AI model. Please try again.",
                "action": "error",
                "success": False,
            }, status=status.HTTP_502_BAD_GATEWAY)

        action = llm_result.get("action", "general_query")
        ai_reply = llm_result.get("reply", "")
        data = llm_result.get("data", {})
        confidence = llm_result.get("confidence", 0)

        # 3. Execute action
        handler = ACTION_HANDLERS.get(action)
        if handler:
            try:
                result = handler(data, request.user)
                return Response({
                    "action": action,
                    "ai_reply": ai_reply,
                    "confidence": confidence,
                    "success": result.get("success", False),
                    "reply": result.get("message", ai_reply),
                    "record_id": result.get("record_id"),
                })
            except Exception as e:
                logger.exception(f"Action handler error for '{action}': {e}")
                return Response({
                    "action": action,
                    "reply": f"❌ Error executing '{action}': {str(e)}",
                    "success": False,
                })
        else:
            # general_query — just return what the AI said
            return Response({
                "action": action,
                "reply": ai_reply or "I'm not sure how to help with that. Try asking me to create a product, sales order, or purchase order.",
                "success": True,
            })


# Keep legacy endpoint for backward compat
class VoiceExtractAPIView(APIView):
    """Legacy schema-based extraction endpoint."""
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        transcript = request.data.get("transcript")
        schema = request.data.get("schema")
        if not transcript or not schema:
            return Response({"error": "transcript and schema are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            requests.get(f"{OLLAMA_URL}/api/tags", timeout=2).raise_for_status()
        except requests.exceptions.RequestException:
            return Response({"error": "Ollama service is unreachable."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        prompt = (
            f"Extract data from the transcript based on the schema. Return ONLY valid JSON.\n\n"
            f"Transcript: {transcript}\n\nSchema:\n{json.dumps(schema, indent=2)}"
        )
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": OLLAMA_MODEL, "prompt": prompt, "format": "json", "stream": False},
                timeout=45,
            )
            response.raise_for_status()
            raw = response.json().get("response", "").strip()
            if raw.startswith("```json"): raw = raw[7:]
            if raw.startswith("```"): raw = raw[3:]
            if raw.endswith("```"): raw = raw[:-3]
            return Response(json.loads(raw.strip()), status=status.HTTP_200_OK)
        except requests.exceptions.Timeout:
            return Response({"error": "Timeout"}, status=status.HTTP_504_GATEWAY_TIMEOUT)
        except (requests.exceptions.RequestException, json.JSONDecodeError) as e:
            logger.error(f"Ollama error: {e}")
            return Response({"error": "Failed to extract data."}, status=status.HTTP_502_BAD_GATEWAY)
