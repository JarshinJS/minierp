"""
views.py for the Products app.

This module contains the views logic for the Products functionality.
"""
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from rest_framework import viewsets, serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from core.exceptions import DomainError
from .models import Product, Category
from .serializers import ProductSerializer, CategorySerializer
from .forms import ProductForm
from . import services
from . import selectors
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import OpenApiParameter, extend_schema
from apps.accounts.permissions import DRFRolePermission, RoleRequiredMixin, roles_for_module

MODULE_ROLES = roles_for_module("products")

# ==============================================================================
# DRF API ViewSets
# ==============================================================================

class ProductViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, DRFRolePermission]
    allowed_roles = MODULE_ROLES
    # Records are cancelled/deactivated via services, never hard-deleted through the API.
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    queryset = Product.objects.all().select_related("category", "default_vendor", "default_bom")
    serializer_class = ProductSerializer

    @extend_schema(parameters=[
        OpenApiParameter("search", str, description="Name or SKU"),
        OpenApiParameter("category", str, description="Category id"),
        OpenApiParameter("status", str, enum=["active", "inactive"]),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        if self.action != "list":
            return super().get_queryset()
        params = self.request.query_params
        return selectors.get_products(
            search_query=params.get("search", "").strip() or None,
            category_id=params.get("category") or None,
            is_active={"active": True, "inactive": False}.get(params.get("status")),
        ).order_by("name")

    @extend_schema(request=None, responses=ProductSerializer)
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """Hide the product from new sales and purchase orders."""
        product = self.get_object()
        services.deactivate_product(product)
        product.refresh_from_db()
        return Response(ProductSerializer(product).data)

    def perform_create(self, serializer):
        try:
            # Delegate model creation strictly to the Service layer
            product = services.create_product(
                name=serializer.validated_data["name"],
                sku=serializer.validated_data["sku"],
                category=serializer.validated_data["category"],
                cost_price=serializer.validated_data["cost_price"],
                selling_price=serializer.validated_data["selling_price"],
                unit_of_measure=serializer.validated_data["unit_of_measure"],
                procure_on_demand=serializer.validated_data.get("procure_on_demand", False),
                procurement_type=serializer.validated_data.get("procurement_type", "PURCHASE"),
                default_vendor=serializer.validated_data.get("default_vendor"),
                default_bom=serializer.validated_data.get("default_bom"),
                is_active=serializer.validated_data.get("is_active", True)
            )
            serializer.instance = product
        except DomainError as e:
            raise serializers.ValidationError({"detail": e.message})

    def perform_update(self, serializer):
        try:
            # Delegate model updates strictly to the Service layer
            product = services.update_product(serializer.instance, **serializer.validated_data)
            serializer.instance = product
        except DomainError as e:
            raise serializers.ValidationError({"detail": e.message})

    @action(detail=True, methods=["get"])
    def stock(self, request, pk=None):
        """
        Stock Endpoint: Fetch read-only stock levels using selectors.
        """
        product = self.get_object()
        data = selectors.get_product_stock(product)
        return Response(data)


class CategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, DRFRolePermission]
    allowed_roles = MODULE_ROLES
    # Records are cancelled/deactivated via services, never hard-deleted through the API.
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

# ==============================================================================
# UI Class-Based Views & HTMX
# ==============================================================================

class ProductUIListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    allowed_roles = MODULE_ROLES
    model = Product
    template_name = "products/product_list.html"
    context_object_name = "products"
    paginate_by = 25

    def get_queryset(self):
        search_query = self.request.GET.get("search")
        category_id = self.request.GET.get("category")
        status = self.request.GET.get("status")
        is_active = {"active": True, "inactive": False}.get(status)
        return selectors.get_products(
            search_query=search_query,
            category_id=category_id,
            is_active=is_active,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all().order_by("name")
        context["selected_category"] = self.request.GET.get("category", "")
        context["search_query"] = self.request.GET.get("search", "")
        context["selected_status"] = self.request.GET.get("status", "")
        return context


class ProductUIDetailView(LoginRequiredMixin, RoleRequiredMixin, DetailView):
    allowed_roles = MODULE_ROLES
    model = Product
    template_name = "products/product_detail.html"
    context_object_name = "product"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Select stock info from database using selector
        context["stock"] = selectors.get_product_stock(self.object)
        return context


class ProductUICreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    allowed_roles = MODULE_ROLES
    model = Product
    form_class = ProductForm
    template_name = "products/product_form.html"
    success_url = reverse_lazy("products:product_list")

    def form_valid(self, form):
        try:
            services.create_product(
                name=form.cleaned_data["name"],
                sku=form.cleaned_data["sku"],
                category=form.cleaned_data["category"],
                cost_price=form.cleaned_data["cost_price"],
                selling_price=form.cleaned_data["selling_price"],
                unit_of_measure=form.cleaned_data["unit_of_measure"],
                procure_on_demand=form.cleaned_data["procure_on_demand"],
                procurement_type=form.cleaned_data["procurement_type"],
                default_vendor=form.cleaned_data["default_vendor"],
                default_bom=form.cleaned_data["default_bom"],
                is_active=form.cleaned_data["is_active"]
            )
            return redirect("products:product_list")
        except DomainError as e:
            form.add_error(None, e.message)
            return self.form_invalid(form)


class ProductUIUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    allowed_roles = MODULE_ROLES
    model = Product
    form_class = ProductForm
    template_name = "products/product_form.html"

    def form_valid(self, form):
        try:
            services.update_product(self.object, **form.cleaned_data)
            return redirect("products:product_detail", pk=self.object.pk)
        except DomainError as e:
            form.add_error(None, e.message)
            return self.form_invalid(form)


class ProductUIDeactivateView(LoginRequiredMixin, RoleRequiredMixin, View):
    allowed_roles = MODULE_ROLES
    def post(self, request, pk, *args, **kwargs):
        product = get_object_or_404(Product, pk=pk)
        try:
            services.deactivate_product(product)
        except DomainError as e:
            return HttpResponseBadRequest(e.message)
            
        # Return updated product row partial to be swapped by HTMX
        return render(request, "products/product_row.html", {"product": product})
