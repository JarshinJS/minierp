from django import forms
from django.forms import inlineformset_factory

from .models import (
    ExportOrder, ExportOrderLine,
    ImportOrder, ImportOrderLine,
    ExportInvoice,
    Shipment,
    TradeDocument,
    TradeCustomer, TradeSupplier,
    Country, Currency, Incoterm,
)

_INPUT = "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand sm:text-sm"
_SELECT = "block w-full pl-3 pr-10 py-2 text-sm border border-slate-300 bg-white focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand rounded-lg"
_TEXTAREA = "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand sm:text-sm"
_DATE = "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand sm:text-sm"
_NUMBER = "appearance-none block w-full px-3 py-1.5 border border-slate-300 rounded-lg shadow-sm focus:outline-none focus:ring-1 focus:ring-brand focus:border-brand text-sm"


# ===========================================================================
# Trade Partners
# ===========================================================================

class TradeCustomerForm(forms.ModelForm):
    class Meta:
        model = TradeCustomer
        fields = ["name", "country", "email", "phone", "tax_id", "address"]
        widgets = {
            "name": forms.TextInput(attrs={"class": _INPUT, "placeholder": "Customer name"}),
            "country": forms.Select(attrs={"class": _SELECT}),
            "email": forms.EmailInput(attrs={"class": _INPUT, "placeholder": "email@example.com"}),
            "phone": forms.TextInput(attrs={"class": _INPUT, "placeholder": "+1-555-0100"}),
            "tax_id": forms.TextInput(attrs={"class": _INPUT, "placeholder": "Tax/VAT ID"}),
            "address": forms.Textarea(attrs={"class": _TEXTAREA, "rows": 3, "placeholder": "Full address"}),
        }


class TradeSupplierForm(forms.ModelForm):
    class Meta:
        model = TradeSupplier
        fields = ["name", "country", "email", "phone", "tax_id", "address"]
        widgets = {
            "name": forms.TextInput(attrs={"class": _INPUT, "placeholder": "Supplier name"}),
            "country": forms.Select(attrs={"class": _SELECT}),
            "email": forms.EmailInput(attrs={"class": _INPUT, "placeholder": "email@example.com"}),
            "phone": forms.TextInput(attrs={"class": _INPUT, "placeholder": "+1-555-0100"}),
            "tax_id": forms.TextInput(attrs={"class": _INPUT, "placeholder": "Tax/VAT ID"}),
            "address": forms.Textarea(attrs={"class": _TEXTAREA, "rows": 3, "placeholder": "Full address"}),
        }


# ===========================================================================
# Export Orders
# ===========================================================================

class ExportOrderForm(forms.ModelForm):
    class Meta:
        model = ExportOrder
        fields = [
            "customer", "country", "currency", "incoterm",
            "shipping_method", "port_of_loading", "port_of_destination",
            "container_details", "notes",
        ]
        widgets = {
            "customer": forms.Select(attrs={"class": _SELECT}),
            "country": forms.Select(attrs={"class": _SELECT}),
            "currency": forms.Select(attrs={"class": _SELECT}),
            "incoterm": forms.Select(attrs={"class": _SELECT}),
            "shipping_method": forms.Select(attrs={"class": _SELECT}),
            "port_of_loading": forms.TextInput(attrs={"class": _INPUT, "placeholder": "e.g. Mumbai Port"}),
            "port_of_destination": forms.TextInput(attrs={"class": _INPUT, "placeholder": "e.g. Rotterdam"}),
            "container_details": forms.Textarea(attrs={"class": _TEXTAREA, "rows": 2, "placeholder": "Container type and details"}),
            "notes": forms.Textarea(attrs={"class": _TEXTAREA, "rows": 3, "placeholder": "Additional notes"}),
        }


class ExportOrderLineForm(forms.ModelForm):
    class Meta:
        model = ExportOrderLine
        fields = ["description", "hs_code", "quantity", "unit_price"]
        widgets = {
            "description": forms.TextInput(attrs={"class": _INPUT, "placeholder": "Item description"}),
            "hs_code": forms.TextInput(attrs={"class": _INPUT, "placeholder": "HS Code"}),
            "quantity": forms.NumberInput(attrs={"step": "0.01", "class": _NUMBER, "placeholder": "0.00"}),
            "unit_price": forms.NumberInput(attrs={"step": "0.01", "class": _NUMBER, "placeholder": "0.00"}),
        }


ExportOrderLineFormSet = inlineformset_factory(
    ExportOrder,
    ExportOrderLine,
    form=ExportOrderLineForm,
    extra=2,
    can_delete=True,
)


# ===========================================================================
# Import Orders
# ===========================================================================

class ImportOrderForm(forms.ModelForm):
    class Meta:
        model = ImportOrder
        fields = [
            "supplier", "country", "currency",
            "container_number", "eta", "notes",
        ]
        widgets = {
            "supplier": forms.Select(attrs={"class": _SELECT}),
            "country": forms.Select(attrs={"class": _SELECT}),
            "currency": forms.Select(attrs={"class": _SELECT}),
            "container_number": forms.TextInput(attrs={"class": _INPUT, "placeholder": "e.g. MSKU1234567"}),
            "eta": forms.DateInput(attrs={"class": _DATE, "type": "date"}),
            "notes": forms.Textarea(attrs={"class": _TEXTAREA, "rows": 3, "placeholder": "Additional notes"}),
        }


class ImportOrderLineForm(forms.ModelForm):
    class Meta:
        model = ImportOrderLine
        fields = ["description", "hs_code", "quantity", "unit_price"]
        widgets = {
            "description": forms.TextInput(attrs={"class": _INPUT, "placeholder": "Item description"}),
            "hs_code": forms.TextInput(attrs={"class": _INPUT, "placeholder": "HS Code"}),
            "quantity": forms.NumberInput(attrs={"step": "0.01", "class": _NUMBER, "placeholder": "0.00"}),
            "unit_price": forms.NumberInput(attrs={"step": "0.01", "class": _NUMBER, "placeholder": "0.00"}),
        }


ImportOrderLineFormSet = inlineformset_factory(
    ImportOrder,
    ImportOrderLine,
    form=ImportOrderLineForm,
    extra=2,
    can_delete=True,
)


# ===========================================================================
# Export Invoice
# ===========================================================================

class ExportInvoiceForm(forms.ModelForm):
    class Meta:
        model = ExportInvoice
        fields = ["amount", "due_date", "notes"]
        widgets = {
            "amount": forms.NumberInput(attrs={"step": "0.01", "class": _NUMBER, "placeholder": "Invoice amount"}),
            "due_date": forms.DateInput(attrs={"class": _DATE, "type": "date"}),
            "notes": forms.Textarea(attrs={"class": _TEXTAREA, "rows": 3, "placeholder": "Invoice notes"}),
        }


# ===========================================================================
# Shipment
# ===========================================================================

class ShipmentForm(forms.ModelForm):
    class Meta:
        model = Shipment
        fields = [
            "carrier", "tracking_number", "vessel_name",
            "port_of_loading", "port_of_destination",
            "departure_date", "arrival_date", "notes",
        ]
        widgets = {
            "carrier": forms.TextInput(attrs={"class": _INPUT, "placeholder": "Carrier name"}),
            "tracking_number": forms.TextInput(attrs={"class": _INPUT, "placeholder": "Tracking number"}),
            "vessel_name": forms.TextInput(attrs={"class": _INPUT, "placeholder": "Vessel/flight name"}),
            "port_of_loading": forms.TextInput(attrs={"class": _INPUT, "placeholder": "Port of loading"}),
            "port_of_destination": forms.TextInput(attrs={"class": _INPUT, "placeholder": "Port of destination"}),
            "departure_date": forms.DateInput(attrs={"class": _DATE, "type": "date"}),
            "arrival_date": forms.DateInput(attrs={"class": _DATE, "type": "date"}),
            "notes": forms.Textarea(attrs={"class": _TEXTAREA, "rows": 3}),
        }


# ===========================================================================
# Trade Document Upload
# ===========================================================================

class TradeDocumentUploadForm(forms.ModelForm):
    class Meta:
        model = TradeDocument
        fields = ["document_type", "title", "file", "notes"]
        widgets = {
            "document_type": forms.Select(attrs={"class": _SELECT}),
            "title": forms.TextInput(attrs={"class": _INPUT, "placeholder": "Document title"}),
            "file": forms.ClearableFileInput(attrs={
                "class": "block w-full text-sm text-slate-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-brand/10 file:text-brand hover:file:bg-brand/20 cursor-pointer",
                "accept": ".pdf,.doc,.docx,.jpg,.jpeg,.png,.xlsx,.xls",
            }),
            "notes": forms.Textarea(attrs={"class": _TEXTAREA, "rows": 2, "placeholder": "Notes about this document"}),
        }
