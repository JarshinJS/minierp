from django.contrib.auth.mixins import LoginRequiredMixin
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


class VendorViewSet(viewsets.ModelViewSet):
    queryset = Vendor.objects.all().order_by("name")
    serializer_class = VendorSerializer


class PurchaseOrderViewSet(viewsets.ModelViewSet):
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


class VendorUIListView(LoginRequiredMixin, ListView):
    model = Vendor
    template_name = "purchase/vendor_list.html"
    context_object_name = "vendors"

    def get_queryset(self):
        return Vendor.objects.all().order_by("name")


class PurchaseOrderUIListView(LoginRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = "purchase/purchase_order_list.html"
    context_object_name = "orders"

    def get_queryset(self):
        return PurchaseOrder.objects.all().select_related("vendor", "created_by").prefetch_related("lines__product").order_by("-created_at")


class PurchaseOrderUICreateView(LoginRequiredMixin, CreateView):
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


class PurchaseOrderUIUpdateView(LoginRequiredMixin, UpdateView):
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


class PurchaseOrderUIConfirmView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        order = get_object_or_404(PurchaseOrder, pk=pk)
        try:
            services.confirm_order(order)
        except (DomainError, WorkflowError) as exc:
            return HttpResponseBadRequest(exc.message)
        return render(request, "purchase/purchase_order_row.html", {"order": order})


class PurchaseOrderUIReceiveView(LoginRequiredMixin, View):
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


class PurchaseOrderUICancelView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        order = get_object_or_404(PurchaseOrder, pk=pk)
        try:
            services.cancel_order(order)
        except (DomainError, WorkflowError) as exc:
            return HttpResponseBadRequest(exc.message)
        return render(request, "purchase/purchase_order_row.html", {"order": order})

