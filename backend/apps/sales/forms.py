from django import forms
from django.forms import inlineformset_factory
from .models import SalesOrder, SalesOrderLine

class SalesOrderForm(forms.ModelForm):
    class Meta:
        model = SalesOrder
        fields = ["customer_name", "notes"]
        widgets = {
            "customer_name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "e.g. Acme Corporation"
            }),
            "notes": forms.Textarea(attrs={
                "rows": 3,
                "class": "form-input",
                "placeholder": "Add any specific instructions..."
            }),
        }


class SalesOrderLineForm(forms.ModelForm):
    class Meta:
        model = SalesOrderLine
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

# Inline formset for inline entry of order lines
SalesOrderLineFormSet = inlineformset_factory(
    SalesOrder,
    SalesOrderLine,
    form=SalesOrderLineForm,
    extra=2,  # Present 2 empty rows by default
    can_delete=True
)
