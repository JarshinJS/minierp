from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from rest_framework import viewsets, serializers, status as rest_status
from rest_framework.decorators import action
from rest_framework.response import Response

from core.exceptions import DomainError, WorkflowError
from .models import SalesOrder, SalesOrderLine, SalesOrderStatus
from .serializers import SalesOrderSerializer
from .forms import SalesOrderForm, SalesOrderLineFormSet
from . import services

# ==============================================================================
# DRF API ViewSets
# ==============================================================================

class SalesOrderViewSet(viewsets.ModelViewSet):
    queryset = SalesOrder.objects.all().prefetch_related("lines__product", "created_by")
    serializer_class = SalesOrderSerializer

    def perform_create(self, serializer):
        # Handled inside Serializer's create() override
        serializer.save()

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        order = self.get_object()
        try:
            services.confirm_order(order)
            return Response(SalesOrderSerializer(order).data)
        except (DomainError, WorkflowError) as e:
            return Response({"detail": e.message}, status=rest_status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def deliver(self, request, pk=None):
        order = self.get_object()
        deliveries_data = request.data.get("deliveries")  # Expects dict: {line_id: quantity}
        try:
            services.deliver_order(order, deliveries_data)
            return Response(SalesOrderSerializer(order).data)
        except (DomainError, WorkflowError) as e:
            return Response({"detail": e.message}, status=rest_status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()
        try:
            services.cancel_order(order)
            return Response(SalesOrderSerializer(order).data)
        except (DomainError, WorkflowError) as e:
            return Response({"detail": e.message}, status=rest_status.HTTP_400_BAD_REQUEST)

# ==============================================================================
# UI Class-Based Views & HTMX
# ==============================================================================

class SalesOrderUIListView(LoginRequiredMixin, ListView):
    model = SalesOrder
    template_name = "sales/sales_order_list.html"
    context_object_name = "orders"

    def get_queryset(self):
        # Order by creation date descending
        return SalesOrder.objects.all().prefetch_related("lines").order_by("-created_at")


class SalesOrderUIKanbanView(LoginRequiredMixin, ListView):
    model = SalesOrder
    template_name = "sales/sales_order_kanban.html"
    context_object_name = "orders"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        orders = self.get_queryset()
        
        # Group orders by status
        kanban = {
            "DRAFT": orders.filter(status=SalesOrderStatus.DRAFT),
            "CONFIRMED": orders.filter(status=SalesOrderStatus.CONFIRMED),
            "PARTIALLY_DELIVERED": orders.filter(status=SalesOrderStatus.PARTIALLY_DELIVERED),
            "FULLY_DELIVERED": orders.filter(status=SalesOrderStatus.FULLY_DELIVERED),
            "CANCELLED": orders.filter(status=SalesOrderStatus.CANCELLED),
        }
        context["kanban"] = kanban
        return context


class SalesOrderUIDetailView(LoginRequiredMixin, DetailView):
    model = SalesOrder
    template_name = "sales/sales_order_detail.html"
    context_object_name = "order"


class SalesOrderUICreateView(LoginRequiredMixin, CreateView):
    model = SalesOrder
    form_class = SalesOrderForm
    template_name = "sales/sales_order_form.html"

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data["lines"] = SalesOrderLineFormSet(self.request.POST)
        else:
            data["lines"] = SalesOrderLineFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        lines = context["lines"]
        if lines.is_valid():
            lines_data = []
            for line_form in lines:
                if line_form.cleaned_data and not line_form.cleaned_data.get("DELETE", False):
                    lines_data.append({
                        "product": line_form.cleaned_data["product"],
                        "quantity": line_form.cleaned_data["quantity"],
                        "unit_price": line_form.cleaned_data["unit_price"]
                    })
            if not lines_data:
                form.add_error(None, "At least one line item is required.")
                return self.form_invalid(form)
            try:
                order = services.create_order(
                    customer_name=form.cleaned_data["customer_name"],
                    created_by=self.request.user,
                    lines_data=lines_data,
                    notes=form.cleaned_data.get("notes", "")
                )
                return redirect("sales:sales_order_detail", pk=order.pk)
            except DomainError as e:
                form.add_error(None, e.message)
                return self.form_invalid(form)
        else:
            return self.form_invalid(form)


class SalesOrderUIUpdateView(LoginRequiredMixin, UpdateView):
    model = SalesOrder
    form_class = SalesOrderForm
    template_name = "sales/sales_order_form.html"

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data["lines"] = SalesOrderLineFormSet(self.request.POST, instance=self.object)
        else:
            data["lines"] = SalesOrderLineFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        if self.object.status != SalesOrderStatus.DRAFT:
            form.add_error(None, "Only DRAFT orders can be edited.")
            return self.form_invalid(form)
            
        context = self.get_context_data()
        lines = context["lines"]
        if lines.is_valid():
            try:
                # Update main SO details
                self.object.customer_name = form.cleaned_data["customer_name"]
                self.object.notes = form.cleaned_data.get("notes", "")
                self.object.save()
                
                # Save Formset lines
                lines.save()
                return redirect("sales:sales_order_detail", pk=self.object.pk)
            except DomainError as e:
                form.add_error(None, e.message)
                return self.form_invalid(form)
        else:
            return self.form_invalid(form)


# ==============================================================================
# HTMX Actions
# ==============================================================================

class SalesOrderUIConfirmView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        order = get_object_or_404(SalesOrder, pk=pk)
        try:
            services.confirm_order(order)
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)
        return render(request, "sales/sales_order_detail_card.html", {"order": order})


class SalesOrderUIDeliverView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        order = get_object_or_404(SalesOrder, pk=pk)
        
        # Check if partial delivery is requested via post parameters
        deliveries = {}
        for key, val in request.POST.items():
            if key.startswith("deliver_qty_"):
                line_id = key.replace("deliver_qty_", "")
                if val:
                    deliveries[line_id] = val
                    
        # If no explicit delivery quantities are specified, default to None (full delivery)
        if not deliveries:
            deliveries = None

        try:
            services.deliver_order(order, deliveries)
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)
        return render(request, "sales/sales_order_detail_card.html", {"order": order})


class SalesOrderUICancelView(LoginRequiredMixin, View):
    def post(self, request, pk, *args, **kwargs):
        order = get_object_or_404(SalesOrder, pk=pk)
        try:
            services.cancel_order(order)
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(e.message)
        return render(request, "sales/sales_order_detail_card.html", {"order": order})
