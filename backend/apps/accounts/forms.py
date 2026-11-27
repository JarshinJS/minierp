from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import User

class SignupForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "form-input",
            "placeholder": "you@example.com"
        })
    )
    full_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            "class": "form-input",
            "placeholder": "John Doe"
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "placeholder": "••••••••"
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "form-input",
            "placeholder": "••••••••"
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise ValidationError("Passwords do not match.")
        if password:
            # Enforce AUTH_PASSWORD_VALIDATORS (length, common passwords, etc.).
            try:
                validate_password(
                    password,
                    user=User(email=cleaned_data.get("email", ""), full_name=cleaned_data.get("full_name", "")),
                )
            except ValidationError as exc:
                self.add_error("password", exc)
        return cleaned_data
