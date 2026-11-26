from django import forms
from .models import Product, Category

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "sku",
            "category",
            "unit_of_measure",
            "cost_price",
            "selling_price",
            "procure_on_demand",
            "procurement_type",
            "default_vendor",
            "default_bom",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "e.g. Wooden Chair"
            }),
            "sku": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "e.g. WCH-001"
            }),
            "category": forms.Select(attrs={
                "class": "form-select"
            }),
            "unit_of_measure": forms.Select(attrs={
                "class": "form-select"
            }),
            "cost_price": forms.NumberInput(attrs={
                "step": "0.01",
                "class": "form-input",
                "placeholder": "0.00"
            }),
            "selling_price": forms.NumberInput(attrs={
                "step": "0.01",
                "class": "form-input",
                "placeholder": "0.00"
            }),
            "procure_on_demand": forms.CheckboxInput(attrs={
                "class": "form-checkbox"
            }),
            "procurement_type": forms.Select(attrs={
                "class": "form-select"
            }),
            "default_vendor": forms.Select(attrs={
                "class": "form-select"
            }),
            "default_bom": forms.Select(attrs={
                "class": "form-select"
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "form-checkbox"
            }),
        }
