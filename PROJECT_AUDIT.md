# Project Audit Report

This report outlines the stabilization audit of the Shiv Furniture Works ERP project to ensure that all modules work together, navigation is intact, and there are no migration or syntax errors.

---

## 1. System Health & Checks

- **Django System Check (`manage.py check`)**: Passed with 0 issues.
- **Database Migrations (`manage.py showmigrations`)**: All migrations are up to date and applied successfully.
- **Tests Execution (`pytest`)**: All 75 test cases passed successfully.

---

## 2. Identified Issues & Fixed Bugs

### 2.1. Critical Template/Attribute Crash on Inventory Page (`/inventory/`) - **FIXED**
- **Error**: Django raised `AttributeError: property 'available_qty' of 'Product' object has no setter` at `/inventory/`.
- **Cause**: The `Product` model defines `available_qty` as a read-only `@property`. However, the queryset inside `InventoryHomeView` annotated the products using `.annotate(available_qty=...)`. During query evaluation, Django tried to call `setattr(product, 'available_qty', ...)` which crashed.
- **Fix**: Renamed the query annotation field name to `avail_qty` in `apps/inventory/views.py` and `apps/dashboard/selectors.py` to prevent naming collision with the `@property`. This allows the template to cleanly invoke `prod.available_qty` (the property) dynamically.

### 2.2. Missing Integration of Inventory URLs in the Root Router - **FIXED**
- **Error**: The URL pattern for the `apps.inventory` module was never registered in `config/urls.py`, resulting in broken navigation sidebar links and unable to resolve `inventory:home`.
- **Fix**: Included `path("inventory/", include("apps.inventory.urls")),` in `config/urls.py`.

### 2.3. Shortage Calculation Logical Bug (Sales Order Confirmation) - **PENDING FIX**
- **Error**: In `apps/sales/services.py:confirm_order()`, the shortage check condition compares `on_hand_qty` directly to the ordered quantity (`on_hand_qty < line.quantity`), ignoring existing stock reservations. This means if stock is already reserved for other orders, new confirmations will fail to trigger procurement requests despite a real shortage of available stock.
- **Recommended Fix**: Check the product's `available_qty` (using `available_qty < 0` after reserving) to calculate shortages.

---

## 3. Missing Modules

According to the ERP specifications:
1. **Phase 7 — Delivery Management** (`apps/delivery/`) is completely missing.
2. **Phase 9 — Reporting** (`apps/reports/`) is completely missing.

---

## 4. Summary of Actions & Next Steps

1. **Bug Fix**: Update `apps/sales/services.py` to calculate shortages using `available_qty`.
2. **Phase 7 — Delivery Management**: Initialize the `delivery` app, including its models, services, views, forms, and tests.
3. **Phase 9 — Reporting**: Initialize the `reports` app.
4. **End-to-End Workflow & Automation**: Ensure all state transitions match the specifications.
