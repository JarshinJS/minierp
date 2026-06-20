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
                "class": "block w-full pl-3 pr-10 py-2 text-base border-slate-300 bg-white focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand sm:text-sm rounded-lg"
            }),
            "notes": forms.Textarea(attrs={
                "rows": 3,
                "class": "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand sm:text-sm",
                "placeholder": "Add internal purchasing notes..."
            }),
        }


class PurchaseOrderLineForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderLine
        fields = ["product", "quantity", "unit_price"]
        widgets = {
            "product": forms.Select(attrs={
                "class": "block w-full pl-3 pr-10 py-1.5 text-sm border border-slate-300 bg-white focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand rounded-lg"
            }),
            "quantity": forms.NumberInput(attrs={
                "step": "0.01",
                "class": "appearance-none block w-full px-3 py-1.5 border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand text-sm",
                "placeholder": "0.0"
            }),
            "unit_price": forms.NumberInput(attrs={
                "step": "0.01",
                "class": "appearance-none block w-full px-3 py-1.5 border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand text-sm",
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