from django import forms
from django.conf import settings

from .models import Product, ReportRequest


class ReportRequestForm(forms.ModelForm):
    class Meta:
        model = ReportRequest
        fields = ["requester_name", "email", "date_from", "date_to", "region", "simulate"]
        widgets = {
            "date_from": forms.DateInput(attrs={"type": "date"}),
            "date_to": forms.DateInput(attrs={"type": "date"}),
        }
        labels = {"requester_name": "Your name", "email": "Send the report to",
                  "date_from": "From", "date_to": "To", "simulate": "Demo failure mode"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not settings.DEBUG:  # failure simulation is a demo-only control
            del self.fields["simulate"]
        for name, f in self.fields.items():
            f.widget.attrs.setdefault("class", "input")

    def clean(self):
        data = super().clean()
        a, b = data.get("date_from"), data.get("date_to")
        if a and b and a > b:
            self.add_error("date_to", "End date must be on or after the start date.")
        return data


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["name", "sku", "price", "original"]
        labels = {"original": "Product photo"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", "input")
