"""
views.py for the Inventory app.

This module contains the views logic for the Inventory functionality.
"""
from decimal import Decimal
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.shortcuts import render, redirect
from django.views import View
from django.views.generic import TemplateView
from django.http import HttpResponse
from django.utils.html import format_html


from apps.products.models import Product, Category
from apps.inventory.models import InventoryLedgerEntry, LedgerEntryType
from apps.inventory import services as inventory_services
from apps.inventory.selectors import get_inventory_stats, get_ledger_entries, get_stock_levels
from core.exceptions import DomainError
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import DRFRolePermission, RoleRequiredMixin, roles_for_module

MODULE_ROLES = roles_for_module("inventory")


def _error_alert(message):
    return HttpResponse(format_html('<div class="alert alert-danger" role="alert">{}</div>', message))


class InventoryHomeView(LoginRequiredMixin, RoleRequiredMixin, TemplateView):
    allowed_roles = MODULE_ROLES
    template_name = "inventory/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request

        # 1. Filters
        search_query = request.GET.get("q", "").strip()
        category_id = request.GET.get("category", "")
        tab = request.GET.get("tab", "stock")  # stock or ledger
        stock_filter = request.GET.get("filter", "")

        # 2. Products with computed stock fields, and headline stats
        products = get_stock_levels(search_query, category_id, stock_filter)
        stats = get_inventory_stats()

        # Paginate products (10 per page)
        page_number = request.GET.get("page", 1)
        products_paginator = Paginator(products, 10)
        products_page = products_paginator.get_page(page_number if tab == "stock" else 1)

        # 4. Get Ledger Entries
        filters_data = {}
        ledger_product_id = request.GET.get("ledger_product", "")
        ledger_entry_type = request.GET.get("ledger_type", "")
        ledger_ref = request.GET.get("ledger_ref", "").strip()

        if ledger_product_id:
            filters_data["product"] = ledger_product_id
        if ledger_entry_type:
            filters_data["entry_type"] = ledger_entry_type
        if ledger_ref:
            filters_data["reference"] = ledger_ref

        ledger_entries = get_ledger_entries(filters_data)
        
        # Paginate ledger entries (10 per page)
        ledger_paginator = Paginator(ledger_entries, 10)
        ledger_page = ledger_paginator.get_page(page_number if tab == "ledger" else 1)

        # 5. Populate Context
        context.update({
            "products": products,
            "paginated_products": products_page,
            "categories": Category.objects.all(),
            "ledger_entries": ledger_entries,
            "paginated_ledger": ledger_page,
            "ledger_types": LedgerEntryType.choices,
            "stats": stats,
            "current_tab": tab,
            "search_query": search_query,
            "category_id": category_id,
            "stock_filter": stock_filter,
            "ledger_product_id": ledger_product_id,
            "ledger_entry_type": ledger_entry_type,
            "ledger_ref": ledger_ref,
        })
        return context


class InventoryAdjustView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = MODULE_ROLES
    def post(self, request, *args, **kwargs):
        product_id = request.POST.get("product_id")
        adjustment_type = request.POST.get("adjustment_type")
        quantity = request.POST.get("quantity")
        reference = request.POST.get("reference", "").strip()

        if not product_id or not adjustment_type or not quantity:
            err_msg = "All fields (product, type, quantity) are required."
            if request.headers.get("HX-Request"):
                return _error_alert(err_msg)
            return HttpResponse(err_msg, status=400)

        try:
            product = Product.objects.get(pk=product_id)
            qty = Decimal(quantity)
            if qty <= 0:
                raise DomainError("Quantity must be a positive number.")

            if adjustment_type == LedgerEntryType.RECEIPT:
                inventory_services.receive_stock(product, qty, reference or "Manual Adjustment (Receipt)")
            elif adjustment_type == LedgerEntryType.ISSUE:
                inventory_services.issue_stock(product, qty, reference or "Manual Adjustment (Issue)")
            else:
                raise DomainError("Invalid adjustment type selected.")

            if request.headers.get("HX-Request"):
                response = HttpResponse(status=204)
                response["HX-Refresh"] = "true"
                return response
            return redirect("inventory:home")

        except Product.DoesNotExist:
            err_msg = "Selected product does not exist."
            if request.headers.get("HX-Request"):
                return _error_alert(err_msg)
            return HttpResponse(err_msg, status=404)

        except DomainError as e:
            err_msg = str(e)
            if request.headers.get("HX-Request"):
                return _error_alert(err_msg)
            return HttpResponse(err_msg, status=400)

        except Exception as e:
            err_msg = f"System error: {str(e)}"
            if request.headers.get("HX-Request"):
                return _error_alert(err_msg)
            return HttpResponse(err_msg, status=500)
