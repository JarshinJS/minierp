"""
views.py for the Delivery app.

This module contains the views logic for the Delivery functionality.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.http import HttpResponseBadRequest, HttpResponse
from django.urls import reverse
from core.exceptions import DomainError, WorkflowError
from apps.accounts.permissions import RoleRequiredMixin
from apps.accounts.models import UserRole
from apps.sales.models import SalesOrder
from .models import DeliveryNote, DeliveryNoteStatus
from . import services

class DeliveryUIListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    model = DeliveryNote
    template_name = "delivery/list.html"
    context_object_name = "deliveries"
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.SALES_USER, UserRole.INVENTORY_MANAGER]

    paginate_by = 20

    def get_queryset(self):
        qs = DeliveryNote.objects.all().select_related("sales_order", "created_by").order_by("-created_at")
        status = self.request.GET.get("status", "")
        if status in DeliveryNoteStatus.values:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        from django.db.models import Count
        context = super().get_context_data(**kwargs)
        counts = dict(DeliveryNote.objects.values_list("status").annotate(n=Count("id")))
        context["selected_status"] = self.request.GET.get("status", "")
        context["status_tabs"] = [("", "All", sum(counts.values()))] + [
            (value, label, counts.get(value, 0)) for value, label in DeliveryNoteStatus.choices
        ]
        return context


class DeliveryUIDetailView(LoginRequiredMixin, RoleRequiredMixin, DetailView):
    model = DeliveryNote
    template_name = "delivery/detail.html"
    context_object_name = "delivery"
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.SALES_USER, UserRole.INVENTORY_MANAGER]


class DeliveryUICreateView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.SALES_USER, UserRole.INVENTORY_MANAGER]

    def post(self, request, pk, *args, **kwargs):
        sales_order = get_object_or_404(SalesOrder, pk=pk)
        
        # Deliver all remaining pending quantities
        lines_data = services.pending_delivery_lines(sales_order)

        if not lines_data:
            return HttpResponseBadRequest("No items pending delivery on this order.")

        try:
            dn = services.create_delivery_note(
                sales_order=sales_order,
                lines_data=lines_data,
                created_by=request.user,
                notes=f"Delivery Note for {sales_order.order_number}"
            )
            return redirect("delivery:detail", pk=dn.pk)
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(str(e))


class DeliveryUIDispatchView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.INVENTORY_MANAGER]

    def post(self, request, pk, *args, **kwargs):
        delivery_note = get_object_or_404(DeliveryNote, pk=pk)
        try:
            services.dispatch_delivery_note(delivery_note, user=request.user)
            if request.headers.get("HX-Request"):
                return render(request, "delivery/partials/delivery_card.html", {"delivery": delivery_note})
            return redirect("delivery:detail", pk=delivery_note.pk)
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(str(e))


class DeliveryUIDeliverView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.INVENTORY_MANAGER, UserRole.SALES_USER]

    def post(self, request, pk, *args, **kwargs):
        delivery_note = get_object_or_404(DeliveryNote, pk=pk)
        try:
            services.deliver_delivery_note(delivery_note, user=request.user)
            if request.headers.get("HX-Request"):
                return render(request, "delivery/partials/delivery_card.html", {"delivery": delivery_note})
            return redirect("delivery:detail", pk=delivery_note.pk)
        except (DomainError, WorkflowError) as e:
            return HttpResponseBadRequest(str(e))
