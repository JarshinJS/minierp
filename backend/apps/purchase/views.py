"""
views.py for the Purchase app.

This module contains the views logic for the Purchase functionality.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView
from rest_framework import status as rest_status, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.exceptions import DomainError, WorkflowError

from . import services
from .forms import PurchaseOrderForm, PurchaseOrderLineFormSet
from .models import PurchaseOrder, PurchaseOrderStatus, Vendor
from .serializers import PurchaseOrderSerializer, VendorSerializer
from rest_framework.permissions import IsAuthenticated
from apps.accounts.permissions import DRFRolePermission, RoleRequiredMixin, roles_for_module

MODULE_ROLES = roles_for_module("purchase")


class VendorViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, DRFRolePermission]
    allowed_roles = MODULE_ROLES
    # Records are cancelled/deactivated via services, never hard-deleted through the API.
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    queryset = Vendor.objects.all().order_by("name")
    serializer_class = VendorSerializer


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, DRFRolePermission]
    allowed_roles = MODULE_ROLES
    # Records are cancelled/deactivated via services, never hard-deleted through the API.
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    queryset = PurchaseOrder.objects.all().select_related("vendor", "created_by").prefetch_related("lines__product")
    serializer_class = PurchaseOrderSerializer

    def perform_create(self, serializer):
        serializer.save()

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        order = self.get_object()
        try:
            services.confirm_order(order)
            return Response(PurchaseOrderSerializer(order).data)
        except (DomainError, WorkflowError) as exc:
            return Response({"detail": exc.message}, status=rest_status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def receive(self, request, pk=None):
        order = self.get_object()
        receipts_data = request.data.get("receipts")
        try:
            services.receive_order(order, receipts_data)
            return Response(PurchaseOrderSerializer(order).data)
        except (DomainError, WorkflowError) as exc:
            return Response({"detail": exc.message}, status=rest_status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        try:
            services.cancel_order(order)
            return Response(PurchaseOrderSerializer(order).data)
        except (DomainError, WorkflowError) as exc:
            return Response({"detail": exc.message}, status=rest_status.HTTP_400_BAD_REQUEST)


class VendorUIListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    allowed_roles = MODULE_ROLES
    model = Vendor
    template_name = "purchase/vendor_list.html"
    context_object_name = "vendors"

    def get_queryset(self):
        return Vendor.objects.all().order_by("name")


class PurchaseOrderUIListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    allowed_roles = MODULE_ROLES
    model = PurchaseOrder
    template_name = "purchase/purchase_order_list.html"
    context_object_name = "orders"
    paginate_by = 10

    def get_queryset(self):
        qs = PurchaseOrder.objects.all().select_related("vendor", "created_by").prefetch_related("lines__product").order_by("-created_at")
        q = self.request.GET.get("q", "").strip()
        status = self.request.GET.get("status", "")
        if q:
            qs = qs.filter(Q(order_number__icontains=q) | Q(vendor__name__icontains=q))
        if status in PurchaseOrderStatus.values:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search_query"] = self.request.GET.get("q", "")
        context["selected_status"] = self.request.GET.get("status", "")
        context["status_choices"] = PurchaseOrderStatus.choices
        return context


class PurchaseOrderUICreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    allowed_roles = MODULE_ROLES
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = "purchase/purchase_order_form.html"

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data["lines"] = PurchaseOrderLineFormSet(self.request.POST)
        else:
            data["lines"] = PurchaseOrderLineFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        lines = context["lines"]
        if not lines.is_valid():
            return self.form_invalid(form)

        lines_data = []
        for line_form in lines:
            if line_form.cleaned_data and not line_form.cleaned_data.get("DELETE", False):
                lines_data.append({
                    "product": line_form.cleaned_data["product"],
                    "quantity": line_form.cleaned_data["quantity"],
                    "unit_price": line_form.cleaned_data["unit_price"],
                })

        if not lines_data:
            form.add_error(None, "At least one line item is required.")
            return self.form_invalid(form)

        try:
            services.create_order(
                vendor=form.cleaned_data["vendor"],
                created_by=self.request.user,
                lines_data=lines_data,
                notes=form.cleaned_data.get("notes", ""),
            )
            return redirect("purchase:purchase_order_list")
        except DomainError as exc:
            form.add_error(None, exc.message)
            return self.form_invalid(form)


class PurchaseOrderUIUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    allowed_roles = MODULE_ROLES
    model = PurchaseOrder
    form_class = PurchaseOrderForm
    template_name = "purchase/purchase_order_form.html"

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data["lines"] = PurchaseOrderLineFormSet(self.request.POST, instance=self.object)
        else:
            data["lines"] = PurchaseOrderLineFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        if self.object.status != PurchaseOrderStatus.DRAFT:
            form.add_error(None, "Only DRAFT purchase orders can be edited.")
            return self.form_invalid(form)

        context = self.get_context_data()
        lines = context["lines"]
        if not lines.is_valid():
            return self.form_invalid(form)

        lines_data = []
        for line_form in lines:
            if line_form.cleaned_data and not line_form.cleaned_data.get("DELETE", False):
                lines_data.append({
                    "product": line_form.cleaned_data["product"],
                    "quantity": line_form.cleaned_data["quantity"],
                    "unit_price": line_form.cleaned_data["unit_price"],
                })

        if not lines_data:
            form.add_error(None, "At least one line item is required.")
            return self.form_invalid(form)

        try:
            services.update_order(
                self.object,
                vendor=form.cleaned_data["vendor"],
                lines_data=lines_data,
                notes=form.cleaned_data.get("notes", ""),
            )
            return redirect("purchase:purchase_order_list")
        except DomainError as exc:
            form.add_error(None, exc.message)
            return self.form_invalid(form)


class PurchaseOrderUIConfirmView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = MODULE_ROLES
    def post(self, request, pk, *args, **kwargs):
        order = get_object_or_404(PurchaseOrder, pk=pk)
        try:
            services.confirm_order(order)
        except (DomainError, WorkflowError) as exc:
            return HttpResponseBadRequest(exc.message)
        return render(request, "purchase/purchase_order_row.html", {"order": order})


class PurchaseOrderUIReceiveView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = MODULE_ROLES
    def post(self, request, pk, *args, **kwargs):
        order = get_object_or_404(PurchaseOrder, pk=pk)
        receipts = {}
        for key, val in request.POST.items():
            if key.startswith("receive_qty_") and val:
                receipts[key.replace("receive_qty_", "")] = val

        if not receipts:
            receipts = None

        try:
            services.receive_order(order, receipts)
        except (DomainError, WorkflowError) as exc:
            return HttpResponseBadRequest(exc.message)
        return render(request, "purchase/purchase_order_row.html", {"order": order})


class PurchaseOrderUICancelView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = MODULE_ROLES
    def post(self, request, pk, *args, **kwargs):
        order = get_object_or_404(PurchaseOrder, pk=pk)
        try:
            services.cancel_order(order)
        except (DomainError, WorkflowError) as exc:
            return HttpResponseBadRequest(exc.message)
        return render(request, "purchase/purchase_order_row.html", {"order": order})

