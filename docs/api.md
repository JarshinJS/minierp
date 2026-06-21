# API Documentation

The Mini ERP System primarily utilizes server-side rendered templates combined with HTMX. However, it exposes specific API endpoints to facilitate advanced features like the Voice Assistant.

## Voice Assistant API

The Voice Assistant API translates natural language transcripts into actionable ERP commands using a local LLM (Ollama).

### Endpoint: `/api/voice/assistant/`

**Method:** `POST`
**Authentication:** Required (User session)

**Description:**
Receives a text transcript (usually derived from speech-to-text on the client), sends it to the local Ollama instance with a predefined system prompt, parses the structured JSON intent, and executes the corresponding ERP action (e.g., creating a sales order, looking up a product, updating stock).

**Request Body:**
```json
{
  "transcript": "Create a new sales order for John Doe with 5 teak chairs"
}
```

**Response Format:**
```json
{
  "action": "create_sales_order",
  "ai_reply": "I have created a sales order for John Doe for 5 teak chairs.",
  "confidence": 0.95,
  "success": true,
  "reply": "✅ Sales Order SO-A1B2C3D4 created for John Doe.\n  • teak chair × 5 @ ₹1500.00",
  "record_id": "e4b5d6..."
}
```

**Supported Actions (Intents):**
- `create_product`: Add a new product to the catalog.
- `create_sales_order`: Create a new sales order.
- `create_purchase_order`: Create a new purchase order.
- `lookup_product`: Search for a product by name.
- `lookup_sales_order`: Search for a sales order by number/customer.
- `lookup_purchase_order`: Search for a purchase order by number/vendor.
- `update_stock`: Increase or decrease the stock levels of a product.
- `general_query`: Fallback for non-actionable queries.

### Legacy Endpoint: `/api/voice/extract/`

**Method:** `POST`
**Authentication:** Required (User session)

**Description:**
A generic extraction endpoint that takes a transcript and a JSON schema, prompting the LLM to extract data from the transcript matching the schema.

**Request Body:**
```json
{
  "transcript": "Add a new vendor named Acme Corp",
  "schema": {
    "vendor_name": "string"
  }
}
```
