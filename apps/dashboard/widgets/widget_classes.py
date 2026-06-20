from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.utils import timezone

from apps.accounts.models import UserRole
from apps.products.models import Product
from apps.sales.models import SalesOrder, SalesOrderStatus
from apps.purchase.models import PurchaseOrder, PurchaseOrderStatus
from apps.manufacturing.models import ManufacturingOrder, MOStatus
from apps.procurement.models import ProcurementRequest, ProcurementStatus
from apps.delivery.models import DeliveryNote, DeliveryNoteStatus
from apps.audit_logs.models import AuditLog, AuditLogAction
from apps.foreign_trade.models import ExportOrder, ImportOrder
from apps.blockchain.models import BlockchainDocument
from . import DashboardWidget

class ProductWidget(DashboardWidget):
    title = "Products Catalog"
    icon = '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/></svg>'
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.SALES_USER, UserRole.PURCHASE_USER, UserRole.INVENTORY_MANAGER]

    def get_data(self, user):
        return {
            "total_products": Product.objects.count(),
            "active_products": Product.objects.filter(is_active=True).count(),
            "inactive_products": Product.objects.filter(is_active=False).count(),
        }


class InventoryWidget(DashboardWidget):
    title = "Inventory Levels"
    icon = '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2"/></svg>'
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.INVENTORY_MANAGER, UserRole.MANUFACTURING_USER]

    def get_data(self, user):
        active_products = Product.objects.filter(is_active=True)
        inventory_value = sum(p.on_hand_qty * p.cost_price for p in active_products)
        total_stock = active_products.aggregate(total=Sum("on_hand_qty"))["total"] or Decimal("0.00")
        reserved_stock = active_products.aggregate(total=Sum("reserved_qty"))["total"] or Decimal("0.00")
        low_stock_count = sum(1 for p in active_products if p.available_qty <= 5.00)

        return {
            "inventory_value": float(inventory_value),
            "total_stock": float(total_stock),
            "reserved_stock": float(reserved_stock),
            "low_stock_count": low_stock_count,
        }


class SalesWidget(DashboardWidget):
    title = "Sales Activity"
    icon = '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.SALES_USER]

    def get_data(self, user):
        today = timezone.now().date()
        this_month = timezone.now().month
        this_year = timezone.now().year

        # Today's sales count & amount
        today_orders = SalesOrder.objects.filter(created_at__date=today).exclude(status=SalesOrderStatus.CANCELLED)
        today_count = today_orders.count()
        today_sales_val = sum(order.total_amount for order in today_orders)

        # Monthly sales amount
        monthly_orders = SalesOrder.objects.filter(created_at__year=this_year, created_at__month=this_month).exclude(status=SalesOrderStatus.CANCELLED)
        monthly_sales_val = sum(order.total_amount for order in monthly_orders)

        pending_orders = SalesOrder.objects.filter(status__in=[
            SalesOrderStatus.DRAFT, 
            SalesOrderStatus.CONFIRMED, 
            SalesOrderStatus.PARTIALLY_DELIVERED
        ]).count()

        delivered_orders = SalesOrder.objects.filter(status=SalesOrderStatus.FULLY_DELIVERED).count()

        return {
            "today_sales_count": today_count,
            "today_sales_value": float(today_sales_val),
            "monthly_sales": float(monthly_sales_val),
            "pending_orders": pending_orders,
            "delivered_orders": delivered_orders,
        }


class PurchaseWidget(DashboardWidget):
    title = "Purchase Activity"
    icon = '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 11V7a4 4 0 00-8 0v4M5 9h14l1 12H4L5 9z"/></svg>'
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.PURCHASE_USER]

    def get_data(self, user):
        purchase_orders = PurchaseOrder.objects.exclude(status=PurchaseOrderStatus.CANCELLED)
        total_purchases_val = sum(po.total_amount for po in purchase_orders)

        pending_pos = PurchaseOrder.objects.filter(status__in=[
            PurchaseOrderStatus.DRAFT,
            PurchaseOrderStatus.CONFIRMED,
            PurchaseOrderStatus.PARTIALLY_RECEIVED
        ]).count()

        received_pos = PurchaseOrder.objects.filter(status=PurchaseOrderStatus.FULLY_RECEIVED).count()

        return {
            "total_purchases_value": float(total_purchases_val),
            "pending_pos": pending_pos,
            "received_pos": received_pos,
        }


class ManufacturingWidget(DashboardWidget):
    title = "Manufacturing Progress"
    icon = '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z"/></svg>'
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.MANUFACTURING_USER]

    def get_data(self, user):
        active_mos = ManufacturingOrder.objects.filter(status=MOStatus.IN_PROGRESS).count()
        planned_mos = ManufacturingOrder.objects.filter(status__in=[MOStatus.DRAFT, MOStatus.CONFIRMED]).count()
        completed_mos = ManufacturingOrder.objects.filter(status=MOStatus.DONE).count()

        return {
            "active_mos": active_mos,
            "planned_mos": planned_mos,
            "completed_mos": completed_mos,
        }


class ProcurementWidget(DashboardWidget):
    title = "Procurement Command"
    icon = '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17a2 2 0 11-4 0 2 2 0 014 0zM19 17a2 2 0 11-4 0 2 2 0 014 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16V6a1 1 0 00-1-1H4a1 1 0 00-1 1v10a1 1 0 001 1h1m8-1a1 1 0 01-1 1H9m4-1V8a1 1 0 011-1h2.586a1 1 0 01.707.293l3.414 3.414a1 1 0 01.293.707V16a1 1 0 01-1 1h-1m-6-1a1 1 0 001 1h1M5 17h5m10 0h-5"/></svg>'
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.PURCHASE_USER, UserRole.INVENTORY_MANAGER]

    def get_data(self, user):
        open_requisitions = ProcurementRequest.objects.filter(status__in=[
            ProcurementStatus.PENDING, 
            ProcurementStatus.IN_PROGRESS
        ]).count()

        open_pos = PurchaseOrder.objects.filter(status__in=[
            PurchaseOrderStatus.CONFIRMED, 
            PurchaseOrderStatus.PARTIALLY_RECEIVED
        ]).count()

        # Delayed POs: Created more than 7 days ago and not fully received/cancelled
        seven_days_ago = timezone.now() - timezone.timedelta(days=7)
        delayed_pos = PurchaseOrder.objects.filter(
            status__in=[PurchaseOrderStatus.CONFIRMED, PurchaseOrderStatus.PARTIALLY_RECEIVED],
            created_at__lt=seven_days_ago
        ).count()

        return {
            "open_requisitions": open_requisitions,
            "open_pos": open_pos,
            "delayed_orders": delayed_pos,
        }


class DeliveryWidget(DashboardWidget):
    title = "Deliveries Control"
    icon = '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"/></svg>'
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.SALES_USER, UserRole.INVENTORY_MANAGER]

    def get_data(self, user):
        pending = DeliveryNote.objects.filter(status=DeliveryNoteStatus.PENDING).count()
        dispatched = DeliveryNote.objects.filter(status=DeliveryNoteStatus.DISPATCHED).count()
        delivered = DeliveryNote.objects.filter(status=DeliveryNoteStatus.DELIVERED).count()

        return {
            "pending_deliveries": pending,
            "dispatched": dispatched,
            "delivered": delivered,
        }


class ReportsWidget(DashboardWidget):
    title = "Reports Output"
    icon = '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-2a2 2 0 00-2-2H5a2 2 0 00-2 2v2a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v8m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z"/></svg>'
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.ACCOUNTANT]

    def get_data(self, user):
        # Count reports exports logged in system
        reports_audit_count = AuditLog.objects.filter(module="reports").count()
        
        return {
            "generated_reports": 9,  # Number of predefined report templates
            "most_used_report": "Stock Asset Valuations" if reports_audit_count > 0 else "Sales Report Daily",
            "recent_exports_count": reports_audit_count,
        }


class AuditWidget(DashboardWidget):
    title = "System Audit Trail"
    icon = '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>'
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER]

    def get_data(self, user):
        today = timezone.now().date()
        today_logs = AuditLog.objects.filter(timestamp__date=today)

        # Login actions count: we check AuditLogAction.STATUS_CHANGED or just count login changes
        login_count = AuditLog.objects.filter(action=AuditLogAction.STATUS_CHANGED, field_changed="last_login").count()

        create_count = AuditLog.objects.filter(action=AuditLogAction.CREATED).count()
        update_count = AuditLog.objects.filter(action=AuditLogAction.UPDATED).count()

        return {
            "today_activities": today_logs.count(),
            "login_count": login_count,
            "create_actions": create_count,
            "update_actions": update_count,
        }


class ForeignTradeWidget(DashboardWidget):
    title = "Foreign Trade & Web3"
    icon = '<svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>'
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER]

    def get_data(self, user):
        exports_count = ExportOrder.objects.count()
        imports_count = ImportOrder.objects.count()
        
        bc_total = BlockchainDocument.objects.count()
        bc_verified = BlockchainDocument.objects.filter(verified=True).count()
        
        return {
            "exports": exports_count,
            "imports": imports_count,
            "bc_total": bc_total,
            "bc_verified": bc_verified,
        }

