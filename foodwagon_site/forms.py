import re

from django import forms

from .models import DeliveryZone


class CheckoutForm(forms.Form):
    customer_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    phone = forms.CharField(
        max_length=32,
        widget=forms.TelInput(attrs={"autocomplete": "tel", "placeholder": "+234…"}),
    )
    fulfilment_method = forms.ChoiceField(
        choices=[("delivery", "Delivery"), ("pickup", "Pickup")],
        widget=forms.RadioSelect,
    )
    delivery_zone = forms.ModelChoiceField(
        queryset=DeliveryZone.objects.none(),
        required=False,
        empty_label="Choose an example delivery area",
    )
    delivery_address = forms.CharField(
        max_length=250,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "autocomplete": "street-address"}),
    )
    special_instructions = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    checkout_token = forms.UUIDField(widget=forms.HiddenInput)
    demo_data_acknowledgement = forms.BooleanField(required=False)
    terms_accepted = forms.BooleanField(required=False)

    def __init__(self, *args, mode="demo", profile=None, **kwargs):
        self.mode = mode
        self.profile = profile
        super().__init__(*args, **kwargs)
        zones = DeliveryZone.objects.filter(is_active=True)
        if mode == "live":
            zones = zones.filter(is_demo=False)
        self.fields["delivery_zone"].queryset = zones.order_by("name")
        self.fields["delivery_zone"].label_from_instance = lambda zone: (
            f"{zone} — ₦{zone.delivery_fee_ngn:.2f}"
        )
        for name, field in self.fields.items():
            if name == "checkout_token":
                continue
            if isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect)):
                field.widget.attrs["class"] = "form-check-input"
                continue
            css_class = "form-select" if name == "delivery_zone" else "form-control"
            field.widget.attrs["class"] = css_class
        self.fields["demo_data_acknowledgement"].required = mode in {"demo", "test"}
        self.fields["terms_accepted"].required = mode == "live"

    def clean_phone(self):
        phone = self.cleaned_data["phone"].strip()
        if not re.fullmatch(r"[+0-9][0-9\s().-]{6,30}", phone):
            raise forms.ValidationError("Enter a valid phone number, including country code where available.")
        digits = re.sub(r"\D", "", phone)
        if not 7 <= len(digits) <= 15:
            raise forms.ValidationError("Enter a phone number containing 7 to 15 digits.")
        return phone

    def clean(self):
        cleaned = super().clean()
        method = cleaned.get("fulfilment_method")
        if method == "delivery":
            if not cleaned.get("delivery_zone"):
                self.add_error("delivery_zone", "Choose an active delivery area.")
            if not cleaned.get("delivery_address"):
                self.add_error("delivery_address", "Enter the delivery address.")
        elif method == "pickup" and self.mode == "live":
            if not self.profile or not self.profile.address.strip():
                self.add_error(None, "A verified pickup address has not been configured.")
        return cleaned
