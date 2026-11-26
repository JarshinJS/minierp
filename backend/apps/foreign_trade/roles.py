"""Role groups for the Foreign Trade module, shared by the HTML views and the API."""
from apps.accounts.models import UserRole as R

# View export/import orders.
ORDER_READ = [R.ADMIN, R.BUSINESS_OWNER, R.TRADE_MANAGER, R.DOCUMENTATION_OFFICER, R.FINANCE_MANAGER, R.AUDITOR]
# Create/edit orders and move them through their workflow.
ORDER_WRITE = [R.ADMIN, R.BUSINESS_OWNER, R.TRADE_MANAGER]
# Raise export invoices.
INVOICE_WRITE = [R.ADMIN, R.BUSINESS_OWNER, R.TRADE_MANAGER, R.FINANCE_MANAGER]
# View documents/shipments, and verify documents against the blockchain.
DOCUMENT_READ = [R.ADMIN, R.BUSINESS_OWNER, R.TRADE_MANAGER, R.DOCUMENTATION_OFFICER, R.AUDITOR]
# Upload documents.
DOCUMENT_WRITE = [R.ADMIN, R.BUSINESS_OWNER, R.TRADE_MANAGER, R.DOCUMENTATION_OFFICER]
# Trade customers and suppliers.
PARTNERS = [R.ADMIN, R.BUSINESS_OWNER, R.TRADE_MANAGER]
# Reference data (countries, currencies, incoterms) needed to fill in any trade form.
REFERENCE_READ = ORDER_READ
