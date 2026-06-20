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

    def get_queryset(self):
        return DeliveryNote.objects.all().select_related("sales_order", "created_by").order_by("-created_at")


class DeliveryUIDetailView(LoginRequiredMixin, RoleRequiredMixin, DetailView):
    model = DeliveryNote
    template_name = "delivery/detail.html"
    context_object_name = "delivery"
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.SALES_USER, UserRole.INVENTORY_MANAGER]


class DeliveryUICreateView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = [UserRole.ADMIN, UserRole.BUSINESS_OWNER, UserRole.SALES_USER, UserRole.INVENTORY_MANAGER]

    def post(self, request, pk, *args, **kwargs):
        sales_order = get_object_or_404(SalesOrder, pk=pk)
        
        # Prepare list of items to deliver (all remaining pending quantities)
        lines_data = []
        for line in sales_order.lines.all():
            if line.pending_delivery_qty > 0:
                lines_data.append({
                    "sales_order_line": line,
                    "quantity": line.pending_delivery_qty
                })

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
            if request.headers.get("HX-Request"):
                return HttpResponse(f'<div class="text-sm font-semibold text-rose-600 bg-rose-50 border border-rose-200 rounded-xl p-3 mb-4">{str(e)}</div>', status=400)
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
            if request.headers.get("HX-Request"):
                return HttpResponse(f'<div class="text-sm font-semibold text-rose-600 bg-rose-50 border border-rose-200 rounded-xl p-3 mb-4">{str(e)}</div>', status=400)
            return HttpResponseBadRequest(str(e))
