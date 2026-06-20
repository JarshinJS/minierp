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
                "class": "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand sm:text-sm",
                "placeholder": "e.g. Wooden Chair"
            }),
            "sku": forms.TextInput(attrs={
                "class": "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand sm:text-sm",
                "placeholder": "e.g. WCH-001"
            }),
            "category": forms.Select(attrs={
                "class": "block w-full pl-3 pr-10 py-2 text-base border-slate-300 bg-white focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand sm:text-sm rounded-lg"
            }),
            "unit_of_measure": forms.Select(attrs={
                "class": "block w-full pl-3 pr-10 py-2 text-base border-slate-300 bg-white focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand sm:text-sm rounded-lg"
            }),
            "cost_price": forms.NumberInput(attrs={
                "step": "0.01",
                "class": "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand sm:text-sm",
                "placeholder": "0.00"
            }),
            "selling_price": forms.NumberInput(attrs={
                "step": "0.01",
                "class": "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand sm:text-sm",
                "placeholder": "0.00"
            }),
            "procure_on_demand": forms.CheckboxInput(attrs={
                "class": "h-4 w-4 text-brand focus:ring-brand border-slate-300 rounded-md"
            }),
            "procurement_type": forms.Select(attrs={
                "class": "block w-full pl-3 pr-10 py-2 text-base border-slate-300 bg-white focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand sm:text-sm rounded-lg"
            }),
            "default_vendor": forms.Select(attrs={
                "class": "block w-full pl-3 pr-10 py-2 text-base border-slate-300 bg-white focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand sm:text-sm rounded-lg"
            }),
            "default_bom": forms.Select(attrs={
                "class": "block w-full pl-3 pr-10 py-2 text-base border-slate-300 bg-white focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand sm:text-sm rounded-lg"
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "h-4 w-4 text-brand focus:ring-brand border-slate-300 rounded-md"
            }),
        }
