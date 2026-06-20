from django import forms
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from .models import UserRole, User

class SignupForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm placeholder-slate-400 focus:outline-none focus:ring-brand focus:border-brand sm:text-sm",
            "placeholder": "you@example.com"
        })
    )
    full_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            "class": "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm placeholder-slate-400 focus:outline-none focus:ring-brand focus:border-brand sm:text-sm",
            "placeholder": "John Doe"
        })
    )
    role = forms.ChoiceField(
        choices=UserRole.choices,
        widget=forms.Select(attrs={
            "class": "block w-full pl-3 pr-10 py-2 text-base border-slate-300 focus:outline-none focus:ring-brand focus:border-brand sm:text-sm rounded-md"
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm placeholder-slate-400 focus:outline-none focus:ring-brand focus:border-brand sm:text-sm",
            "placeholder": "••••••••"
        })
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm placeholder-slate-400 focus:outline-none focus:ring-brand focus:border-brand sm:text-sm",
            "placeholder": "••••••••"
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            raise ValidationError("Passwords do not match.")
        return cleaned_data


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm placeholder-slate-400 focus:outline-none focus:ring-brand focus:border-brand sm:text-sm",
            "placeholder": "you@example.com"
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm placeholder-slate-400 focus:outline-none focus:ring-brand focus:border-brand sm:text-sm",
            "placeholder": "••••••••"
        })
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if email and password:
            self.user_cache = authenticate(self.request, email=email, password=password)
            if self.user_cache is None:
                raise ValidationError("Invalid email or password.")
            elif not self.user_cache.is_active:
                raise ValidationError("This account is inactive.")
        return cleaned_data

    def get_user(self):
        return self.user_cache


class VerifyOTPForm(forms.Form):
    otp = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            "class": "appearance-none block w-full px-3 py-2 border border-slate-300 rounded-md shadow-sm placeholder-slate-400 focus:outline-none focus:ring-brand focus:border-brand sm:text-sm text-center tracking-widest text-lg font-bold",
            "placeholder": "••••••",
            "autocomplete": "one-time-code"
        })
    )
