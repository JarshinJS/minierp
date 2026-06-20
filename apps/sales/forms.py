from django import forms
from django.forms import inlineformset_factory
from .models import SalesOrder, SalesOrderLine

class SalesOrderForm(forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = ["customer_name", "notes"]
        widgets = {
            "customer_name": forms.TextInput(attrs={
                "class": "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand sm:text-sm",
                "placeholder": "e.g. Acme Corporation"
            }),
            "notes": forms.Textarea(attrs={
                "rows": 3,
                "class": "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand sm:text-sm",
                "placeholder": "Add any specific instructions..."
            }),
        }


class SalesOrderLineForm(forms.ModelForm):
    class Meta:
        model = SalesOrderLine
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

# Inline formset for inline entry of order lines
SalesOrderLineFormSet = inlineformset_factory(
    SalesOrder,
    SalesOrderLine,
    form=SalesOrderLineForm,
    extra=2,  # Present 2 empty rows by default
    can_delete=True
)
