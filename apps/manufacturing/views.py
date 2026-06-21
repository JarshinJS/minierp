"""
views.py for the Manufacturing app.

This module contains the views logic for the Manufacturing functionality.
"""
import json

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView

from rest_framework import viewsets, serializers as drf_serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from core.exceptions import DomainError
from apps.products.models import Product

from .models import BoM, WorkCenter
from .serializers import BOMSerializer, BOMWriteSerializer, WorkCenterSerializer
from .forms import BOMHeaderForm, WorkCenterForm
from . import services, selectors


# ===========================================================================
# DRF API ViewSets
# ===========================================================================

class WorkCenterViewSet(viewsets.ModelViewSet):
    queryset = WorkCenter.objects.all()
    serializer_class = WorkCenterSerializer

    def perform_create(self, serializer):
        try:
            wc = services.create_work_center(
                name=serializer.validated_data["name"],
                code=serializer.validated_data["code"],
                cost_per_hour=serializer.validated_data.get("cost_per_hour", "0.00"),
            )
            serializer.instance = wc
        except DomainError as e:
            raise drf_serializers.ValidationError({"detail": e.message})

    def perform_update(self, serializer):
        try:
            wc = services.update_work_center(serializer.instance, **serializer.validated_data)
            serializer.instance = wc
        except DomainError as e:
            raise drf_serializers.ValidationError({"detail": e.message})


class BOMViewSet(viewsets.ModelViewSet):
    queryset = BoM.objects.select_related("product").prefetch_related(
        "components__component", "operations__work_center"
    )

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return BOMWriteSerializer
        return BOMSerializer

    def perform_create(self, serializer):
        try:
            bom = services.create_bom(
                name=serializer.validated_data["name"],
                reference=serializer.validated_data["reference"],
                product=serializer.validated_data.get("product"),
                product_qty=serializer.validated_data.get("product_qty", "1.00"),
                notes=serializer.validated_data.get("notes", ""),
                components=[],
                operations=[],
            )
            serializer.instance = bom
        except DomainError as e:
            raise drf_serializers.ValidationError({"detail": e.message})

    def perform_update(self, serializer):
        try:
            bom = services.update_bom(
                serializer.instance,
                name=serializer.validated_data.get("name"),
                product=serializer.validated_data.get("product"),
                product_qty=serializer.validated_data.get("product_qty"),
                notes=serializer.validated_data.get("notes"),
            )
            serializer.instance = bom
        except DomainError as e:
            raise drf_serializers.ValidationError({"detail": e.message})

    @action(detail=True, methods=["get"])
    def cost(self, request, pk=None):
        """Returns total material cost for a BOM."""
        bom = self.get_object()
        total = selectors.get_bom_cost(bom)
        return Response({"bom_id": str(bom.pk), "reference": bom.reference, "total_cost": str(total)})


# ===========================================================================
# UI CBVs — Bill of Materials
# ===========================================================================

def _parse_json_field(request, field_name, label):
    """Parse a JSON hidden field submitted from Alpine.js."""
    raw = request.POST.get(field_name, "[]")
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError
        return data
    except (ValueError, json.JSONDecodeError):
        raise DomainError(f"Invalid {label} data submitted.")


class BOMListView(LoginRequiredMixin, ListView):
    template_name = "manufacturing/bom_list.html"
    context_object_name = "boms"

    def get_queryset(self):
        return selectors.get_boms(
            search=self.request.GET.get("search"),
            active_only=self.request.GET.get("show_inactive") != "1",
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_query"] = self.request.GET.get("search", "")
        ctx["show_inactive"] = self.request.GET.get("show_inactive", "")
        return ctx


class BOMDetailView(LoginRequiredMixin, DetailView):
    template_name = "manufacturing/bom_detail.html"
    context_object_name = "bom"

    def get_object(self):
        return selectors.get_bom(self.kwargs["pk"])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        bom = self.object
        ctx["total_cost"] = selectors.get_bom_cost(bom)
        ctx["total_time"] = selectors.get_bom_operation_time(bom)
        return ctx


class BOMCreateView(LoginRequiredMixin, View):
    template_name = "manufacturing/bom_form.html"

    def _context(self, form=None):
        return {
            "form": form or BOMHeaderForm(),
            "products": Product.objects.filter(is_active=True).order_by("name"),
            "work_centers": selectors.get_work_centers(),
            "existing_components": "[]",
            "existing_operations": "[]",
            "page_title": "Create Bill of Materials",
            "submit_label": "Create BOM",
        }

    def get(self, request):
        return render(request, self.template_name, self._context())

    def post(self, request):
        form = BOMHeaderForm(request.POST)
        try:
            components = _parse_json_field(request, "components_json", "components")
            operations = _parse_json_field(request, "operations_json", "operations")
        except DomainError as e:
            form.add_error(None, e.message)
            return render(request, self.template_name, self._context(form))

        if not form.is_valid():
            return render(request, self.template_name, self._context(form))

        try:
            services.create_bom(
                name=form.cleaned_data["name"],
                reference=form.cleaned_data["reference"],
                product=form.cleaned_data.get("product"),
                product_qty=form.cleaned_data["product_qty"],
                notes=form.cleaned_data.get("notes", ""),
                components=components,
                operations=operations,
            )
            return redirect("manufacturing:bom_list")
        except DomainError as e:
            form.add_error(None, e.message)
            ctx = self._context(form)
            ctx["existing_components"] = json.dumps(components)
            ctx["existing_operations"] = json.dumps(operations)
            return render(request, self.template_name, ctx)


class BOMUpdateView(LoginRequiredMixin, View):
    template_name = "manufacturing/bom_form.html"

    def _get_bom(self, pk):
        return get_object_or_404(BoM, pk=pk)

    def _build_components_json(self, bom):
        return json.dumps([
            {
                "component_id": str(c.component.pk),
                "component_name": f"{c.component.name} ({c.component.sku})",
                "quantity": str(c.quantity),
                "uom": c.uom,
                "sequence": c.sequence,
            }
            for c in bom.components.select_related("component").order_by("sequence")
        ])

    def _build_operations_json(self, bom):
        return json.dumps([
            {
                "work_center_id": str(op.work_center.pk),
                "work_center_name": str(op.work_center),
                "name": op.name,
                "duration_minutes": str(op.duration_minutes),
                "sequence": op.sequence,
            }
            for op in bom.operations.select_related("work_center").order_by("sequence")
        ])

    def _context(self, bom, form=None, components_json=None, operations_json=None):
        return {
            "form": form or BOMHeaderForm(instance=bom),
            "bom": bom,
            "products": Product.objects.filter(is_active=True).order_by("name"),
            "work_centers": selectors.get_work_centers(),
            "existing_components": components_json or self._build_components_json(bom),
            "existing_operations": operations_json or self._build_operations_json(bom),
            "page_title": f"Edit BOM: {bom.reference}",
            "submit_label": "Save Changes",
        }

    def get(self, request, pk):
        bom = self._get_bom(pk)
        return render(request, self.template_name, self._context(bom))

    def post(self, request, pk):
        bom = self._get_bom(pk)
        form = BOMHeaderForm(request.POST, instance=bom)

        try:
            components = _parse_json_field(request, "components_json", "components")
            operations = _parse_json_field(request, "operations_json", "operations")
        except DomainError as e:
            form.add_error(None, e.message)
            return render(request, self.template_name, self._context(bom, form))

        if not form.is_valid():
            return render(request, self.template_name, self._context(
                bom, form,
                json.dumps(components),
                json.dumps(operations),
            ))

        try:
            services.update_bom(
                bom,
                name=form.cleaned_data["name"],
                product=form.cleaned_data.get("product"),
                product_qty=form.cleaned_data["product_qty"],
                notes=form.cleaned_data.get("notes", ""),
                components=components,
                operations=operations,
            )
            return redirect("manufacturing:bom_detail", pk=bom.pk)
        except DomainError as e:
            form.add_error(None, e.message)
            return render(request, self.template_name, self._context(
                bom, form,
                json.dumps(components),
                json.dumps(operations),
            ))


class BOMDeactivateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        bom = get_object_or_404(BoM, pk=pk)
        try:
            services.deactivate_bom(bom)
        except DomainError as e:
            return HttpResponseBadRequest(e.message)
        return render(request, "manufacturing/bom_row.html", {"bom": bom})


# ===========================================================================
# UI CBVs — Work Centers
# ===========================================================================

class WorkCenterListView(LoginRequiredMixin, ListView):
    template_name = "manufacturing/workcenter_list.html"
    context_object_name = "work_centers"

    def get_queryset(self):
        show_inactive = self.request.GET.get("show_inactive") == "1"
        return selectors.get_work_centers(active_only=not show_inactive)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["show_inactive"] = self.request.GET.get("show_inactive", "")
        return ctx


class WorkCenterCreateView(LoginRequiredMixin, View):
    template_name = "manufacturing/workcenter_form.html"

    def get(self, request):
        return render(request, self.template_name, {
            "form": WorkCenterForm(),
            "page_title": "Add Work Center",
            "submit_label": "Create Work Center",
        })

    def post(self, request):
        form = WorkCenterForm(request.POST)
        if form.is_valid():
            try:
                services.create_work_center(
                    name=form.cleaned_data["name"],
                    code=form.cleaned_data["code"],
                    cost_per_hour=form.cleaned_data["cost_per_hour"],
                )
                return redirect("manufacturing:workcenter_list")
            except DomainError as e:
                form.add_error(None, e.message)
        return render(request, self.template_name, {
            "form": form,
            "page_title": "Add Work Center",
            "submit_label": "Create Work Center",
        })


class WorkCenterUpdateView(LoginRequiredMixin, View):
    template_name = "manufacturing/workcenter_form.html"

    def _get_wc(self, pk):
        return get_object_or_404(WorkCenter, pk=pk)

    def get(self, request, pk):
        wc = self._get_wc(pk)
        return render(request, self.template_name, {
            "form": WorkCenterForm(instance=wc),
            "wc": wc,
            "page_title": f"Edit Work Center: {wc.name}",
            "submit_label": "Save Changes",
        })

    def post(self, request, pk):
        wc = self._get_wc(pk)
        form = WorkCenterForm(request.POST, instance=wc)
        if form.is_valid():
            try:
                services.update_work_center(wc, **form.cleaned_data)
                return redirect("manufacturing:workcenter_list")
            except DomainError as e:
                form.add_error(None, e.message)
        return render(request, self.template_name, {
            "form": form,
            "wc": wc,
            "page_title": f"Edit Work Center: {wc.name}",
            "submit_label": "Save Changes",
        })


# ===========================================================================
# DRF API — Manufacturing Orders
# ===========================================================================

from .models import ManufacturingOrder, WorkOrder, MOStatus, WorkOrderStatus
from .serializers import (
    ManufacturingOrderSerializer, ManufacturingOrderWriteSerializer,
    WorkOrderSerializer,
)
from .forms import ManufacturingOrderForm, ProduceForm


class ManufacturingOrderViewSet(viewsets.ModelViewSet):
    queryset = ManufacturingOrder.objects.select_related("product", "bom").prefetch_related(
        "components__product", "work_orders__work_center"
    )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ManufacturingOrderWriteSerializer
        return ManufacturingOrderSerializer

    def perform_create(self, serializer):
        try:
            mo = services.create_mo(
                product=serializer.validated_data["product"],
                qty_to_produce=serializer.validated_data["qty_to_produce"],
                bom=serializer.validated_data.get("bom"),
                scheduled_date=serializer.validated_data.get("scheduled_date"),
                notes=serializer.validated_data.get("notes", ""),
            )
            serializer.instance = mo
        except DomainError as e:
            raise drf_serializers.ValidationError({"detail": str(e)})

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        mo = self.get_object()
        try:
            services.confirm_mo(mo)
        except DomainError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ManufacturingOrderSerializer(mo).data)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        mo = self.get_object()
        try:
            services.start_mo(mo)
        except DomainError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ManufacturingOrderSerializer(mo).data)

    @action(detail=True, methods=["post"])
    def produce(self, request, pk=None):
        mo = self.get_object()
        qty = request.data.get("qty_produced")
        if not qty:
            return Response({"detail": "qty_produced is required."}, status=400)
        try:
            services.produce_mo(mo, qty)
        except DomainError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ManufacturingOrderSerializer(mo).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        mo = self.get_object()
        try:
            services.cancel_mo(mo)
        except DomainError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(ManufacturingOrderSerializer(mo).data)


class WorkOrderViewSet(viewsets.ModelViewSet):
    serializer_class = WorkOrderSerializer
    queryset = WorkOrder.objects.select_related("mo", "work_center")

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        wo = self.get_object()
        try:
            services.start_work_order(wo)
        except DomainError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(WorkOrderSerializer(wo).data)

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        wo = self.get_object()
        try:
            services.complete_work_order(wo, duration_actual=request.data.get("duration_actual"))
        except DomainError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(WorkOrderSerializer(wo).data)


# ===========================================================================
# UI CBVs — Manufacturing Orders
# ===========================================================================

class MOListView(LoginRequiredMixin, ListView):
    template_name = "manufacturing/mo_list.html"
    context_object_name = "mos"
    paginate_by = 10

    def get_queryset(self):
        return selectors.get_manufacturing_orders(
            search=self.request.GET.get("search"),
            status=self.request.GET.get("status") or None,
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["search_query"] = self.request.GET.get("search", "")
        ctx["selected_status"] = self.request.GET.get("status", "")
        ctx["status_choices"] = MOStatus.choices
        return ctx


class MODetailView(LoginRequiredMixin, View):
    template_name = "manufacturing/mo_detail.html"

    def get(self, request, pk):
        mo = selectors.get_manufacturing_order(pk)
        return render(request, self.template_name, {
            "mo": mo,
            "work_orders": selectors.get_work_orders_for_mo(mo),
            "produce_form": ProduceForm(),
        })


class MOCreateView(LoginRequiredMixin, View):
    template_name = "manufacturing/mo_form.html"

    def get(self, request):
        return render(request, self.template_name, {
            "form": ManufacturingOrderForm(),
            "page_title": "Create Manufacturing Order",
            "submit_label": "Create MO",
        })

    def post(self, request):
        form = ManufacturingOrderForm(request.POST)
        if form.is_valid():
            try:
                mo = services.create_mo(
                    product=form.cleaned_data["product"],
                    qty_to_produce=form.cleaned_data["qty_to_produce"],
                    bom=form.cleaned_data.get("bom"),
                    scheduled_date=form.cleaned_data.get("scheduled_date"),
                    notes=form.cleaned_data.get("notes", ""),
                )
                return redirect("manufacturing:mo_detail", pk=mo.pk)
            except DomainError as e:
                form.add_error(None, str(e))
        return render(request, self.template_name, {
            "form": form,
            "page_title": "Create Manufacturing Order",
            "submit_label": "Create MO",
        })


class MOUpdateView(LoginRequiredMixin, View):
    """Edit a DRAFT MO's header fields."""
    template_name = "manufacturing/mo_form.html"

    def _get_mo(self, pk):
        return get_object_or_404(ManufacturingOrder, pk=pk)

    def get(self, request, pk):
        mo = self._get_mo(pk)
        if not mo.is_editable:
            return redirect("manufacturing:mo_detail", pk=mo.pk)
        return render(request, self.template_name, {
            "form": ManufacturingOrderForm(instance=mo),
            "mo": mo,
            "page_title": f"Edit MO: {mo.reference}",
            "submit_label": "Save Changes",
        })

    def post(self, request, pk):
        mo = self._get_mo(pk)
        if not mo.is_editable:
            return redirect("manufacturing:mo_detail", pk=mo.pk)
        form = ManufacturingOrderForm(request.POST, instance=mo)
        if form.is_valid():
            # Only DRAFT MOs can be edited — update fields directly (no service needed)
            try:
                mo.product       = form.cleaned_data["product"]
                mo.qty_to_produce = form.cleaned_data["qty_to_produce"]
                mo.bom           = form.cleaned_data.get("bom")
                mo.scheduled_date = form.cleaned_data.get("scheduled_date")
                mo.notes         = form.cleaned_data.get("notes", "")
                mo.save()
                return redirect("manufacturing:mo_detail", pk=mo.pk)
            except Exception as e:
                form.add_error(None, str(e))
        return render(request, self.template_name, {
            "form": form,
            "mo": mo,
            "page_title": f"Edit MO: {mo.reference}",
            "submit_label": "Save Changes",
        })


class MOConfirmView(LoginRequiredMixin, View):
    def post(self, request, pk):
        mo = get_object_or_404(ManufacturingOrder, pk=pk)
        try:
            services.confirm_mo(mo)
        except DomainError as e:
            # Re-render detail with error message
            return render(request, "manufacturing/mo_detail.html", {
                "mo": selectors.get_manufacturing_order(pk),
                "work_orders": selectors.get_work_orders_for_mo(mo),
                "produce_form": ProduceForm(),
                "error": str(e),
            })
        return redirect("manufacturing:mo_detail", pk=mo.pk)


class MOStartView(LoginRequiredMixin, View):
    def post(self, request, pk):
        mo = get_object_or_404(ManufacturingOrder, pk=pk)
        try:
            services.start_mo(mo)
        except DomainError as e:
            return redirect("manufacturing:mo_detail", pk=mo.pk)
        return redirect("manufacturing:mo_detail", pk=mo.pk)


class MOProduceView(LoginRequiredMixin, View):
    def post(self, request, pk):
        mo = get_object_or_404(ManufacturingOrder, pk=pk)
        form = ProduceForm(request.POST)
        if form.is_valid():
            try:
                services.produce_mo(mo, form.cleaned_data["qty_produced"])
                return redirect("manufacturing:mo_detail", pk=mo.pk)
            except DomainError as e:
                return render(request, "manufacturing/mo_detail.html", {
                    "mo": selectors.get_manufacturing_order(pk),
                    "work_orders": selectors.get_work_orders_for_mo(mo),
                    "produce_form": form,
                    "produce_error": str(e),
                })
        return redirect("manufacturing:mo_detail", pk=mo.pk)


class MOCancelView(LoginRequiredMixin, View):
    def post(self, request, pk):
        mo = get_object_or_404(ManufacturingOrder, pk=pk)
        try:
            services.cancel_mo(mo)
        except DomainError as e:
            pass  # Redirect regardless; error is visible on detail page
        return redirect("manufacturing:mo_list")


class WorkOrderStartView(LoginRequiredMixin, View):
    def post(self, request, pk):
        wo = get_object_or_404(WorkOrder, pk=pk)
        try:
            services.start_work_order(wo)
        except DomainError:
            pass
        return redirect("manufacturing:mo_detail", pk=wo.mo.pk)


class WorkOrderCompleteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        wo = get_object_or_404(WorkOrder, pk=pk)
        duration_actual = request.POST.get("duration_actual") or None
        try:
            services.complete_work_order(wo, duration_actual=duration_actual)
        except DomainError:
            pass
        return redirect("manufacturing:mo_detail", pk=wo.mo.pk)
