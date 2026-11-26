"""
views.py for the Foreign_trade app.

This module contains the views logic for the Foreign_trade functionality.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView

from apps.accounts.permissions import RoleRequiredMixin
from apps.blockchain.models import BlockchainAuditLog, BlockchainDocument
from core.exceptions import DomainError, WorkflowError

from .models import (
    ExportOrder, ExportOrderStatus,
    ImportOrder, ImportOrderStatus,
    TradeDocument, Shipment,
    TradeCustomer, TradeSupplier,
    ExportInvoice,
)
from .forms import (
    ExportOrderForm, ExportOrderLineFormSet,
    ImportOrderForm, ImportOrderLineFormSet,
    ExportInvoiceForm, ShipmentForm,
    TradeDocumentUploadForm,
    TradeCustomerForm, TradeSupplierForm,
)
from . import roles, services, workflows


# ===========================================================================
# Export Order Views
# ===========================================================================

class ExportOrderListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = ExportOrder
    template_name = "foreign_trade/export_order_list.html"
    context_object_name = "orders"
    paginate_by = 10
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER", "DOCUMENTATION_OFFICER", "FINANCE_MANAGER", "AUDITOR"]

    def get_queryset(self):
        qs = ExportOrder.objects.select_related("customer", "country", "currency").order_by("-created_at")
        q = self.request.GET.get("q", "").strip()
        status_filter = self.request.GET.get("status", "")
        if q:
            qs = qs.filter(order_number__icontains=q) | qs.filter(customer__name__icontains=q)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = ExportOrderStatus.choices
        ctx["current_status"] = self.request.GET.get("status", "")
        ctx["search_query"] = self.request.GET.get("q", "")
        return ctx


class ExportOrderDetailView(LoginRequiredMixin, RoleRequiredMixin, DetailView):
    model = ExportOrder
    template_name = "foreign_trade/export_order_detail.html"
    context_object_name = "order"
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER", "DOCUMENTATION_OFFICER", "FINANCE_MANAGER", "AUDITOR"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        order = self.object
        ct = ContentType.objects.get_for_model(ExportOrder)
        ctx["documents"] = TradeDocument.objects.filter(content_type=ct, object_id=order.id).order_by("-created_at")
        ctx["shipments"] = Shipment.objects.filter(content_type=ct, object_id=order.id).order_by("-created_at")
        ctx["invoices"] = order.invoices.all().order_by("-created_at")
        ctx["blockchain_docs"] = BlockchainDocument.objects.filter(
            document__content_type=ct, document__object_id=order.id
        ).select_related("document").order_by("-created_at")
        ctx["audit_logs"] = BlockchainAuditLog.objects.filter(
            reference_id=str(order.id)
        ).order_by("-created_at")[:10]
        return ctx


class ExportOrderCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    model = ExportOrder
    form_class = ExportOrderForm
    template_name = "foreign_trade/export_order_form.html"
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER"]

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data["lines"] = ExportOrderLineFormSet(self.request.POST or None)
        data["form_title"] = "Create Export Order"
        return data

    def form_valid(self, form):
        ctx = self.get_context_data()
        lines_formset = ctx["lines"]
        if lines_formset.is_valid():
            lines_data = []
            for lf in lines_formset:
                if lf.cleaned_data and not lf.cleaned_data.get("DELETE", False):
                    lines_data.append({
                        "description": lf.cleaned_data["description"],
                        "hs_code": lf.cleaned_data.get("hs_code", ""),
                        "quantity": lf.cleaned_data["quantity"],
                        "unit_price": lf.cleaned_data["unit_price"],
                    })
            if not lines_data:
                form.add_error(None, "At least one line item is required.")
                return self.form_invalid(form)
            try:
                order = workflows.create_export(
                    self.request.user,
                    customer=form.cleaned_data["customer"],
                    country=form.cleaned_data["country"],
                    currency=form.cleaned_data["currency"],
                    lines_data=lines_data,
                    incoterm=form.cleaned_data.get("incoterm"),
                    shipping_method=form.cleaned_data.get("shipping_method", "SEA"),
                    port_of_loading=form.cleaned_data.get("port_of_loading", ""),
                    port_of_destination=form.cleaned_data.get("port_of_destination", ""),
                    container_details=form.cleaned_data.get("container_details", ""),
                    notes=form.cleaned_data.get("notes", ""),
                )
                return redirect("foreign_trade:export_order_detail", pk=order.pk)
            except DomainError as e:
                form.add_error(None, e.message)
                return self.form_invalid(form)
        return self.form_invalid(form)


class ExportOrderUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    model = ExportOrder
    form_class = ExportOrderForm
    template_name = "foreign_trade/export_order_form.html"
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER"]

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data["lines"] = ExportOrderLineFormSet(self.request.POST or None, instance=self.object)
        data["form_title"] = "Edit Export Order"
        return data

    def form_valid(self, form):
        if self.object.status != ExportOrderStatus.DRAFT:
            form.add_error(None, "Only DRAFT export orders can be edited.")
            return self.form_invalid(form)
        ctx = self.get_context_data()
        lines_formset = ctx["lines"]
        if lines_formset.is_valid():
            self.object = form.save()
            lines_formset.save()
            return redirect("foreign_trade:export_order_detail", pk=self.object.pk)
        return self.form_invalid(form)


class _ExportActionView(LoginRequiredMixin, RoleRequiredMixin, View):
    """POST-only workflow step on an export order; re-renders the order card."""
    allowed_roles = roles.ORDER_WRITE

    def run(self, request, order):
        raise NotImplementedError

    def post(self, request, pk):
        order = get_object_or_404(ExportOrder, pk=pk)
        try:
            self.run(request, order)
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)
        return render(request, "foreign_trade/partials/export_order_card.html", {"order": order})


def _shipment_data(request):
    return {
        "carrier": request.POST.get("carrier", ""),
        "tracking_number": request.POST.get("tracking_number", ""),
        "vessel_name": request.POST.get("vessel_name", ""),
    }


class ExportOrderConfirmView(_ExportActionView):
    def run(self, request, order):
        workflows.confirm_export(order, request.user)


class ExportOrderShipView(_ExportActionView):
    def run(self, request, order):
        workflows.ship_export(order, _shipment_data(request), request.user)


class ExportOrderDeliverView(_ExportActionView):
    def run(self, request, order):
        workflows.deliver_export(order, request.user)


class ExportOrderCancelView(_ExportActionView):
    def run(self, request, order):
        workflows.cancel_export(order, request.user)


class ExportInvoiceCreateView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER", "FINANCE_MANAGER"]

    def get(self, request, pk):
        order = get_object_or_404(ExportOrder, pk=pk)
        form = ExportInvoiceForm(initial={"amount": order.total_amount})
        return render(request, "foreign_trade/export_invoice_form.html", {"order": order, "form": form})

    def post(self, request, pk):
        order = get_object_or_404(ExportOrder, pk=pk)
        form = ExportInvoiceForm(request.POST)
        if form.is_valid():
            try:
                workflows.create_invoice(
                    order, request.user,
                    amount=form.cleaned_data["amount"],
                    due_date=form.cleaned_data.get("due_date"),
                    notes=form.cleaned_data.get("notes", ""),
                )
                return redirect("foreign_trade:export_order_detail", pk=order.pk)
            except (DomainError, WorkflowError) as e:
                form.add_error(None, e.message)
        return render(request, "foreign_trade/export_invoice_form.html", {"order": order, "form": form})


# ===========================================================================
# Import Order Views
# ===========================================================================

class ImportOrderListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = ImportOrder
    template_name = "foreign_trade/import_order_list.html"
    context_object_name = "orders"
    paginate_by = 10
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER", "DOCUMENTATION_OFFICER", "FINANCE_MANAGER", "AUDITOR"]

    def get_queryset(self):
        qs = ImportOrder.objects.select_related("supplier", "country", "currency").order_by("-created_at")
        q = self.request.GET.get("q", "").strip()
        status_filter = self.request.GET.get("status", "")
        if q:
            qs = qs.filter(order_number__icontains=q) | qs.filter(supplier__name__icontains=q)
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs.distinct()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["status_choices"] = ImportOrderStatus.choices
        ctx["current_status"] = self.request.GET.get("status", "")
        ctx["search_query"] = self.request.GET.get("q", "")
        return ctx


class ImportOrderDetailView(LoginRequiredMixin, RoleRequiredMixin, DetailView):
    model = ImportOrder
    template_name = "foreign_trade/import_order_detail.html"
    context_object_name = "order"
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER", "DOCUMENTATION_OFFICER", "FINANCE_MANAGER", "AUDITOR"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        order = self.object
        ct = ContentType.objects.get_for_model(ImportOrder)
        ctx["documents"] = TradeDocument.objects.filter(content_type=ct, object_id=order.id).order_by("-created_at")
        ctx["shipments"] = Shipment.objects.filter(content_type=ct, object_id=order.id).order_by("-created_at")
        ctx["audit_logs"] = BlockchainAuditLog.objects.filter(
            reference_id=str(order.id)
        ).order_by("-created_at")[:10]
        return ctx


class ImportOrderCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    model = ImportOrder
    form_class = ImportOrderForm
    template_name = "foreign_trade/import_order_form.html"
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER"]

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data["lines"] = ImportOrderLineFormSet(self.request.POST or None)
        data["form_title"] = "Create Import Order"
        return data

    def form_valid(self, form):
        ctx = self.get_context_data()
        lines_formset = ctx["lines"]
        if lines_formset.is_valid():
            lines_data = []
            for lf in lines_formset:
                if lf.cleaned_data and not lf.cleaned_data.get("DELETE", False):
                    lines_data.append({
                        "description": lf.cleaned_data["description"],
                        "hs_code": lf.cleaned_data.get("hs_code", ""),
                        "quantity": lf.cleaned_data["quantity"],
                        "unit_price": lf.cleaned_data["unit_price"],
                    })
            if not lines_data:
                form.add_error(None, "At least one line item is required.")
                return self.form_invalid(form)
            try:
                order = workflows.create_import(
                    self.request.user,
                    supplier=form.cleaned_data["supplier"],
                    country=form.cleaned_data["country"],
                    currency=form.cleaned_data["currency"],
                    lines_data=lines_data,
                    container_number=form.cleaned_data.get("container_number", ""),
                    eta=form.cleaned_data.get("eta"),
                    notes=form.cleaned_data.get("notes", ""),
                )
                return redirect("foreign_trade:import_order_detail", pk=order.pk)
            except DomainError as e:
                form.add_error(None, e.message)
                return self.form_invalid(form)
        return self.form_invalid(form)


class ImportOrderUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    model = ImportOrder
    form_class = ImportOrderForm
    template_name = "foreign_trade/import_order_form.html"
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER"]

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data["lines"] = ImportOrderLineFormSet(self.request.POST or None, instance=self.object)
        data["form_title"] = "Edit Import Order"
        return data

    def form_valid(self, form):
        if self.object.status != ImportOrderStatus.DRAFT:
            form.add_error(None, "Only DRAFT import orders can be edited.")
            return self.form_invalid(form)
        ctx = self.get_context_data()
        lines_formset = ctx["lines"]
        if lines_formset.is_valid():
            self.object = form.save()
            lines_formset.save()
            return redirect("foreign_trade:import_order_detail", pk=self.object.pk)
        return self.form_invalid(form)


class _ImportActionView(LoginRequiredMixin, RoleRequiredMixin, View):
    """POST-only workflow step on an import order; re-renders the order card."""
    allowed_roles = roles.ORDER_WRITE

    def run(self, request, order):
        raise NotImplementedError

    def post(self, request, pk):
        order = get_object_or_404(ImportOrder, pk=pk)
        try:
            self.run(request, order)
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)
        return render(request, "foreign_trade/partials/import_order_card.html", {"order": order})


class ImportOrderConfirmView(_ImportActionView):
    def run(self, request, order):
        workflows.confirm_import(order, request.user)


class ImportOrderTransitView(_ImportActionView):
    def run(self, request, order):
        workflows.transit_import(order, _shipment_data(request), request.user)


class ImportOrderCustomsView(_ImportActionView):
    def run(self, request, order):
        workflows.customs_import(order, request.user)


class ImportOrderReceiveView(_ImportActionView):
    def run(self, request, order):
        workflows.receive_import(order, request.user)


class ImportOrderCancelView(_ImportActionView):
    def run(self, request, order):
        workflows.cancel_import(order, request.user)


# ===========================================================================
# Document Views
# ===========================================================================

class DocumentUploadView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER", "DOCUMENTATION_OFFICER"]

    def get(self, request, order_type, pk):
        order = self._get_order(order_type, pk)
        form = TradeDocumentUploadForm()
        return render(request, "foreign_trade/document_upload.html", {
            "order": order, "form": form, "order_type": order_type
        })

    def post(self, request, order_type, pk):
        order = self._get_order(order_type, pk)
        form = TradeDocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            workflows.upload_document(
                order, request.user,
                file=form.cleaned_data["file"],
                document_type=form.cleaned_data["document_type"],
                title=form.cleaned_data["title"],
                notes=form.cleaned_data.get("notes", ""),
            )
            detail_view = "foreign_trade:export_order_detail" if order_type == "export" else "foreign_trade:import_order_detail"
            return redirect(detail_view, pk=order.pk)
        return render(request, "foreign_trade/document_upload.html", {
            "order": order, "form": form, "order_type": order_type
        })

    def _get_order(self, order_type, pk):
        if order_type == "export":
            return get_object_or_404(ExportOrder, pk=pk)
        return get_object_or_404(ImportOrder, pk=pk)


class DocumentVerifyView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = roles.DOCUMENT_READ

    def post(self, request, pk):
        doc = get_object_or_404(TradeDocument, pk=pk)
        result = workflows.verify(doc, request.user)
        return render(request, "foreign_trade/partials/document_verify_result.html", {
            "result": result, "document": doc,
        })


class DocumentHistoryView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER", "DOCUMENTATION_OFFICER", "AUDITOR"]

    def get(self, request, order_type, pk):
        if order_type == "export":
            order = get_object_or_404(ExportOrder, pk=pk)
        else:
            order = get_object_or_404(ImportOrder, pk=pk)
        documents = services.get_document_history(order)
        return render(request, "foreign_trade/document_history.html", {
            "order": order, "documents": documents, "order_type": order_type,
        })


# ===========================================================================
# Shipment Views
# ===========================================================================

class ShipmentListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = Shipment
    template_name = "foreign_trade/shipment_list.html"
    context_object_name = "shipments"
    paginate_by = 10
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER", "DOCUMENTATION_OFFICER", "AUDITOR"]

    def get_queryset(self):
        qs = Shipment.objects.select_related("content_type", "created_by").order_by("-created_at")
        status_filter = self.request.GET.get("status", "")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def get_context_data(self, **kwargs):
        from .models import ShipmentStatus
        ctx = super().get_context_data(**kwargs)
        ctx["shipment_status_choices"] = ShipmentStatus.choices
        return ctx


class ShipmentDetailView(LoginRequiredMixin, RoleRequiredMixin, DetailView):
    model = Shipment
    template_name = "foreign_trade/shipment_detail.html"
    context_object_name = "shipment"
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER", "DOCUMENTATION_OFFICER", "AUDITOR"]


# ===========================================================================
# Customer & Supplier Views
# ===========================================================================

class TradeCustomerListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = TradeCustomer
    template_name = "foreign_trade/customer_list.html"
    context_object_name = "customers"
    paginate_by = 10
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER"]

    def get_queryset(self):
        qs = TradeCustomer.objects.filter(is_active=True).select_related("country").order_by("name")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(name__icontains=q)
        return qs


class TradeCustomerCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    model = TradeCustomer
    form_class = TradeCustomerForm
    template_name = "foreign_trade/customer_form.html"
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER"]

    def get_success_url(self):
        return self.object.get_absolute_url() if hasattr(self.object, "get_absolute_url") else "/trade/customers/"

    def form_valid(self, form):
        self.object = form.save()
        return redirect("foreign_trade:customer_list")


class TradeSupplierListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = TradeSupplier
    template_name = "foreign_trade/supplier_list.html"
    context_object_name = "suppliers"
    paginate_by = 10
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER"]

    def get_queryset(self):
        qs = TradeSupplier.objects.filter(is_active=True).select_related("country").order_by("name")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(name__icontains=q)
        return qs


class TradeSupplierCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    model = TradeSupplier
    form_class = TradeSupplierForm
    template_name = "foreign_trade/supplier_form.html"
    allowed_roles = ["ADMIN", "BUSINESS_OWNER", "TRADE_MANAGER"]

    def form_valid(self, form):
        self.object = form.save()
        return redirect("foreign_trade:supplier_list")
