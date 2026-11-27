# API Documentation

Every REST endpoint lives under **`/api/`**. The Next.js frontend proxies
`/api/*` to the Django backend, so the browser treats the API as same-origin.

- **OpenAPI schema:** `GET /api/schema/` (login required). Generate it offline with
  `python manage.py spectacular --file schema.yaml` (from `backend/`), e.g. for
  TypeScript codegen with `openapi-typescript`.
- **Interactive docs:** `GET /api/docs/` (Swagger UI, login required).

## Conventions

**Authentication: session cookie + CSRF.**
1. `GET /api/auth/csrf/` once; it sets the `csrftoken` cookie.
2. `POST /api/auth/login/` with `{"email", "password"}` and header `X-CSRFToken: <csrftoken>`.
3. Send `X-CSRFToken` on every `POST`/`PUT`/`PATCH` request after that.

In production the frontend's origin must be listed in `CSRF_TRUSTED_ORIGINS`
on the backend, or Django rejects the request (403).

**Permissions.** Every endpoint requires login with an **approved** account, and
checks the user's role (see the matrix in [architecture.md](architecture.md#role-and-permission-matrix)).
`GET /api/auth/me/` returns `modules` (what the user can open) and `capabilities`
(write actions such as `products.write`, `inventory.adjust`, `accounts.manage`); use
them to build the UI. The API enforces the same rules. `ADMIN` can access everything.

**Account status.** New signups are `PENDING` until an Admin/Business Owner approves
them. For a correct password on a blocked account, `auth/login/` answers `403` with
`{"detail", "code"}` where `code` is `account_pending`, `account_rejected`,
`account_suspended` or `account_disabled`. The same body is returned (and the session
ended) if an existing session's account becomes blocked.

**Errors.** `400` with `{"detail": "..."}` for business-rule violations (for example,
"Only DRAFT orders can be edited."), or `{"<field>": ["..."]}` for validation
errors. `403` means not logged in, account not approved, or role not allowed. `429`
means the request was rate-limited (login/signup: 10 per minute per IP; login also 30
per hour per account, by default).

**Lists** are paginated with `?limit=&offset=` and return
`{"count", "next", "previous", "results"}`. Small lookup lists (roles,
countries, currencies, incoterms, invoices) are returned as plain arrays.

**No hard deletes.** Records are cancelled or deactivated through actions or
`PATCH {"is_active": false}`; `DELETE` returns `405`.

## Endpoints

| Area | Endpoint | Methods | Notes |
|---|---|---|---|
| Auth | `auth/csrf/` | GET | Sets CSRF cookie |
| | `auth/login/`, `auth/logout/` | POST | |
| | `auth/me/` | GET | Current user + `modules` + `capabilities` + `account_status` |
| | `auth/signup/` → `auth/signup/verify/` | POST | Emails a 6-digit code; `resend/` for a new one |
| Users | `users/` | GET | `?search=&role=&is_active=&account_status=` (Admin/Owner) |
| | `users/{id}/approve/` | POST | `{"role"}` required; pending/rejected → approved |
| | `users/{id}/reject/`, `suspend/` | POST | Optional `{"note"}` |
| | `users/{id}/reinstate/` | POST | Suspended → approved |
| | `users/{id}/activate/`, `deactivate/`, `change-role/` | POST | Not on your own account; Admin/Owner accounts and roles are Admin-only |
| | `users/roles/` | GET | Role choices |
| Products | `products/`, `categories/` | GET POST PUT PATCH | `products/{id}/stock/` |
| Purchase | `vendors/`, `purchase-orders/` | GET POST PUT PATCH | `confirm/`, `receive/`, `cancel/` actions |
| Sales | `sales-orders/` | GET POST PUT PATCH | `confirm/`, `deliver/`, `cancel/` actions |
| Inventory | `inventory/stock/` | GET | `?search=&category=&stock=low_stock\|out_of_stock` |
| | `inventory/stock/summary/` | GET | Totals, stock value, low/out-of-stock counts |
| | `inventory/ledger/` | GET | `?product=&entry_type=&reference=` |
| | `inventory/adjustments/` | POST | `{"product", "adjustment_type": "RECEIPT"\|"ISSUE", "quantity", "reference"}` |
| Delivery | `deliveries/` | GET POST | POST `{"sales_order", "lines"?}`; omit `lines` to deliver all pending |
| | `deliveries/{id}/dispatch/`, `deliver/` | POST | Dispatch: Admin/Owner/Inventory Manager |
| Procurement | `procurement/triggers/` | GET | `?status=`; `summary/` for counts |
| Manufacturing | `work-centers/`, `boms/`, `manufacturing-orders/`, `work-orders/` | GET POST PUT PATCH | MO: `confirm/ start/ produce/ cancel/`; WO: `start/ complete/`; BOM: `cost/` |
| Reports | `reports/` | GET | Overview + catalogue of reports |
| | `reports/{category}/{type}/` | GET | JSON `{columns, rows}`; add `?format=csv` to download |
| Dashboard | `dashboard/summary/`, `dashboard/analytics/`, `dashboard/alerts/` | GET | |
| Audit | `audit-logs/` | GET | Filterable audit trail |
| Trade | `trade/exports/` | GET POST PUT PATCH | `confirm/ ship/ deliver/ cancel/`; `invoices/` (GET, POST); edits only while DRAFT |
| | `trade/imports/` | GET POST PUT PATCH | `confirm/ transit/ customs/ receive/ cancel/` |
| | `trade/documents/` | GET POST | POST is multipart upload (pdf/doc/docx/jpg/png/xls/xlsx, ≤10 MB, content-checked); `{id}/verify/` |
| | `trade/documents/{id}/download/?token=` | GET | The document's `file` field is this signed link (user-bound, expires in 5 min) |
| | `trade/shipments/` | GET | |
| | `trade/customers/`, `trade/suppliers/` | GET POST PUT PATCH | `?search=` |
| | `trade/countries/`, `trade/currencies/`, `trade/incoterms/` | GET | Reference data |
| Blockchain | `blockchain/documents/`, `blockchain/audit-logs/` | GET | |
| Voice | `voice/assistant/`, `voice/extract/` | POST | See below |

Reports available: `sales/{daily,monthly,customer}`, `purchase/{summary,vendor}`,
`manufacturing/{efficiency,consumption}`, `inventory/{ledger,valuation,low_stock}`.

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
