from django import forms
from django.forms import inlineformset_factory

from .models import PurchaseOrder, PurchaseOrderLine, Vendor


class VendorForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ["name", "code", "contact_name", "email"]


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ["vendor", "notes"]
        widgets = {
            "vendor": forms.Select(attrs={
                "class": "form-select"
            }),
            "notes": forms.Textarea(attrs={
                "rows": 3,
                "class": "form-input",
                "placeholder": "Add internal purchasing notes..."
            }),
        }


class PurchaseOrderLineForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderLine
        fields = ["product", "quantity", "unit_price"]
        widgets = {
            "product": forms.Select(attrs={
                "class": "form-select"
            }),
            "quantity": forms.NumberInput(attrs={
                "step": "0.01",
                "class": "form-input",
                "placeholder": "0.0"
            }),
            "unit_price": forms.NumberInput(attrs={
                "step": "0.01",
                "class": "form-input",
                "placeholder": "0.00"
            }),
        }


PurchaseOrderLineFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderLine,
    form=PurchaseOrderLineForm,
    extra=2,
    can_delete=True,
)