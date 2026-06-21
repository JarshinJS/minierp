from decimal import Decimal
from django import forms
from decimal import Decimal
from .models import BoM, WorkCenter
from apps.products.models import Product

FIELD_CLASS = (
    "block w-full border border-slate-300 rounded-lg px-3 py-2 text-sm "
    "focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand"
)


class WorkCenterForm(forms.ModelForm):
    class Meta:
        model = WorkCenter
        fields = ["name", "code", "cost_per_hour", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "block w-full border border-slate-300 rounded-lg px-3 py-2 text-sm "
                         "focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand",
                "placeholder": "e.g. CNC Cutting Station",
            }),
            "code": forms.TextInput(attrs={
                "class": "block w-full border border-slate-300 rounded-lg px-3 py-2 text-sm "
                         "focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand uppercase",
                "placeholder": "e.g. WC-CNC",
            }),
            "cost_per_hour": forms.NumberInput(attrs={
                "class": "block w-full border border-slate-300 rounded-lg px-3 py-2 text-sm "
                         "focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand",
                "step": "0.01", "min": "0",
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "h-4 w-4 text-brand border-slate-300 rounded",
            }),
        }


class BOMHeaderForm(forms.ModelForm):
    """
    Handles only the BOM header fields. Components and operations are
    submitted as JSON from Alpine.js and handled separately in the view.
    """
    class Meta:
        model = BoM
        fields = ["name", "reference", "product", "product_qty", "notes"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "block w-full border border-slate-300 rounded-lg px-3 py-2 text-sm "
                         "focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand",
                "placeholder": "e.g. Solid Oak Dining Table",
            }),
            "reference": forms.TextInput(attrs={
                "class": "block w-full border border-slate-300 rounded-lg px-3 py-2 text-sm "
                         "focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand uppercase",
                "placeholder": "e.g. BOM-001",
            }),
            "product": forms.Select(attrs={
                "class": "block w-full border border-slate-300 rounded-lg px-3 py-2 text-sm "
                         "focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand bg-white",
            }),
            "product_qty": forms.NumberInput(attrs={
                "class": "block w-full border border-slate-300 rounded-lg px-3 py-2 text-sm "
                         "focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand",
                "step": "0.01", "min": "0.01",
            }),
            "notes": forms.Textarea(attrs={
                "class": "block w-full border border-slate-300 rounded-lg px-3 py-2 text-sm "
                         "focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand",
                "rows": 3,
                "placeholder": "Optional notes about this BOM…",
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(is_active=True).order_by("name")
        self.fields["product"].required = False
        self.fields["product"].empty_label = "— No finished product (template) —"


# ===========================================================================
# Manufacturing Order Forms
# ===========================================================================

from .models import ManufacturingOrder, BoM as _BoM  # noqa: F811


class ManufacturingOrderForm(forms.ModelForm):
    """Header form for creating / editing a Manufacturing Order."""

    class Meta:
        model = ManufacturingOrder
        fields = ["product", "qty_to_produce", "bom", "scheduled_date", "notes"]
        widgets = {
            "product": forms.Select(attrs={"class": FIELD_CLASS}),
            "bom": forms.Select(attrs={"class": FIELD_CLASS}),
            "qty_to_produce": forms.NumberInput(
                attrs={"class": FIELD_CLASS, "step": "0.01", "min": "0.01", "placeholder": "e.g. 10"}
            ),
            "scheduled_date": forms.DateInput(attrs={"class": FIELD_CLASS, "type": "date"}),
            "notes": forms.Textarea(
                attrs={"class": FIELD_CLASS, "rows": 3, "placeholder": "Optional production notes…"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(is_active=True).order_by("name")
        self.fields["bom"].queryset = _BoM.objects.filter(is_active=True).order_by("reference")
        self.fields["bom"].required = False
        self.fields["bom"].empty_label = "— No BOM (manual) —"
        self.fields["scheduled_date"].required = False
        self.fields["notes"].required = False


class ProduceForm(forms.Form):
    """Form for recording partial or full production on an MO."""
    qty_produced = forms.DecimalField(
        label="Quantity to Produce",
        min_value=Decimal("0.01"),
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            "class": FIELD_CLASS, "step": "0.01", "min": "0.01",
            "placeholder": "Enter quantity produced in this batch…",
            "autofocus": True,
        }),
    )
