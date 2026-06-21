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
from apps.blockchain.services.verification_service import register_document, verify_document, log_audit_event
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
from . import services


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
                order = services.create_export_order(
                    customer=form.cleaned_data["customer"],
                    country=form.cleaned_data["country"],
                    currency=form.cleaned_data["currency"],
                    lines_data=lines_data,
                    created_by=self.request.user,
                    incoterm=form.cleaned_data.get("incoterm"),
                    shipping_method=form.cleaned_data.get("shipping_method", "SEA"),
                    port_of_loading=form.cleaned_data.get("port_of_loading", ""),
                    port_of_destination=form.cleaned_data.get("port_of_destination", ""),
                    container_details=form.cleaned_data.get("container_details", ""),
                    notes=form.cleaned_data.get("notes", ""),
                )
                log_audit_event(
                    event_type=BlockchainAuditLog.EventType.ORDER_CREATED,
                    reference_id=str(order.id),
                    reference_model="ExportOrder",
                    user=self.request.user,
                    metadata={"order_number": order.order_number},
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


class ExportOrderConfirmView(LoginRequiredMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(ExportOrder, pk=pk)
        try:
            services.confirm_export_order(order, user=request.user)
            log_audit_event(
                event_type=BlockchainAuditLog.EventType.ORDER_CONFIRMED,
                reference_id=str(order.id), reference_model="ExportOrder",
                user=request.user, metadata={"order_number": order.order_number},
            )
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)
        return render(request, "foreign_trade/partials/export_order_card.html", {"order": order})


class ExportOrderShipView(LoginRequiredMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(ExportOrder, pk=pk)
        shipment_data = {
            "carrier": request.POST.get("carrier", ""),
            "tracking_number": request.POST.get("tracking_number", ""),
            "vessel_name": request.POST.get("vessel_name", ""),
        }
        try:
            order, shipment = services.ship_export_order(order, shipment_data, user=request.user)
            log_audit_event(
                event_type=BlockchainAuditLog.EventType.SHIPMENT_DISPATCHED,
                reference_id=str(order.id), reference_model="ExportOrder",
                user=request.user,
                metadata={"order_number": order.order_number, "shipment": shipment.shipment_number},
            )
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)
        return render(request, "foreign_trade/partials/export_order_card.html", {"order": order})


class ExportOrderDeliverView(LoginRequiredMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(ExportOrder, pk=pk)
        try:
            services.deliver_export_order(order, user=request.user)
            log_audit_event(
                event_type=BlockchainAuditLog.EventType.SHIPMENT_DELIVERED,
                reference_id=str(order.id), reference_model="ExportOrder",
                user=request.user, metadata={"order_number": order.order_number},
            )
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)
        return render(request, "foreign_trade/partials/export_order_card.html", {"order": order})


class ExportOrderCancelView(LoginRequiredMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(ExportOrder, pk=pk)
        try:
            services.cancel_export_order(order, user=request.user)
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)
        return render(request, "foreign_trade/partials/export_order_card.html", {"order": order})


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
                invoice = services.create_export_invoice(
                    order, user=request.user,
                    amount=form.cleaned_data["amount"],
                    due_date=form.cleaned_data.get("due_date"),
                    notes=form.cleaned_data.get("notes", ""),
                )
                log_audit_event(
                    event_type=BlockchainAuditLog.EventType.INVOICE_GENERATED,
                    reference_id=str(invoice.id), reference_model="ExportInvoice",
                    user=request.user,
                    metadata={"invoice_number": invoice.invoice_number, "order_number": order.order_number},
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
                order = services.create_import_order(
                    supplier=form.cleaned_data["supplier"],
                    country=form.cleaned_data["country"],
                    currency=form.cleaned_data["currency"],
                    lines_data=lines_data,
                    created_by=self.request.user,
                    container_number=form.cleaned_data.get("container_number", ""),
                    eta=form.cleaned_data.get("eta"),
                    notes=form.cleaned_data.get("notes", ""),
                )
                log_audit_event(
                    event_type=BlockchainAuditLog.EventType.ORDER_CREATED,
                    reference_id=str(order.id),
                    reference_model="ImportOrder",
                    user=self.request.user,
                    metadata={"order_number": order.order_number},
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


class ImportOrderConfirmView(LoginRequiredMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(ImportOrder, pk=pk)
        try:
            services.confirm_import_order(order, user=request.user)
            log_audit_event(
                event_type=BlockchainAuditLog.EventType.ORDER_CONFIRMED,
                reference_id=str(order.id), reference_model="ImportOrder",
                user=request.user, metadata={"order_number": order.order_number},
            )
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)
        return render(request, "foreign_trade/partials/import_order_card.html", {"order": order})


class ImportOrderTransitView(LoginRequiredMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(ImportOrder, pk=pk)
        shipment_data = {
            "carrier": request.POST.get("carrier", ""),
            "tracking_number": request.POST.get("tracking_number", ""),
            "vessel_name": request.POST.get("vessel_name", ""),
        }
        try:
            order, shipment = services.transit_import_order(order, shipment_data, user=request.user)
            log_audit_event(
                event_type=BlockchainAuditLog.EventType.SHIPMENT_DISPATCHED,
                reference_id=str(order.id), reference_model="ImportOrder",
                user=request.user, metadata={"order_number": order.order_number},
            )
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)
        return render(request, "foreign_trade/partials/import_order_card.html", {"order": order})


class ImportOrderCustomsView(LoginRequiredMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(ImportOrder, pk=pk)
        try:
            services.customs_import_order(order, user=request.user)
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)
        return render(request, "foreign_trade/partials/import_order_card.html", {"order": order})


class ImportOrderReceiveView(LoginRequiredMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(ImportOrder, pk=pk)
        try:
            services.receive_import_order(order, user=request.user)
            log_audit_event(
                event_type=BlockchainAuditLog.EventType.CUSTOMS_CLEARED,
                reference_id=str(order.id), reference_model="ImportOrder",
                user=request.user, metadata={"order_number": order.order_number},
            )
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)
        return render(request, "foreign_trade/partials/import_order_card.html", {"order": order})


class ImportOrderCancelView(LoginRequiredMixin, View):
    def post(self, request, pk):
        order = get_object_or_404(ImportOrder, pk=pk)
        try:
            services.cancel_import_order(order, user=request.user)
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)
        return render(request, "foreign_trade/partials/import_order_card.html", {"order": order})


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
            doc = services.upload_document(
                file=form.cleaned_data["file"],
                document_type=form.cleaned_data["document_type"],
                related_order=order,
                uploaded_by=request.user,
                title=form.cleaned_data["title"],
                notes=form.cleaned_data.get("notes", ""),
            )
            # Register on blockchain
            try:
                register_document(doc)
                log_audit_event(
                    event_type=BlockchainAuditLog.EventType.DOCUMENT_UPLOADED,
                    reference_id=str(doc.id), reference_model="TradeDocument",
                    user=request.user,
                    metadata={"title": doc.title, "type": doc.document_type},
                )
            except Exception:
                pass  # Document saved even if blockchain fails
            detail_view = "foreign_trade:export_order_detail" if order_type == "export" else "foreign_trade:import_order_detail"
            return redirect(detail_view, pk=order.pk)
        return render(request, "foreign_trade/document_upload.html", {
            "order": order, "form": form, "order_type": order_type
        })

    def _get_order(self, order_type, pk):
        if order_type == "export":
            return get_object_or_404(ExportOrder, pk=pk)
        return get_object_or_404(ImportOrder, pk=pk)


class DocumentVerifyView(LoginRequiredMixin, View):
    def post(self, request, pk):
        doc = get_object_or_404(TradeDocument, pk=pk)
        result = verify_document(doc)
        if result["verified"]:
            log_audit_event(
                event_type=BlockchainAuditLog.EventType.DOCUMENT_VERIFIED,
                reference_id=str(doc.id), reference_model="TradeDocument",
                user=request.user, metadata={"title": doc.title, "status": "verified"},
            )
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
        qs = Shipment.objects.all().order_by("-created_at")
        status_filter = self.request.GET.get("status", "")
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs


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
