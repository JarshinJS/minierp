from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import UserRole
from .permissions import MODULE_ACCESS

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    role_display = serializers.CharField(source="get_role_display", read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "full_name", "role", "role_display",
            "is_active", "is_staff", "last_login", "created_at",
        ]
        read_only_fields = fields


class CurrentUserSerializer(UserSerializer):
    """The logged-in user plus the modules their role can access (drives the frontend menu)."""
    modules = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["modules"]
        read_only_fields = fields

    def get_modules(self, user) -> list[str]:
        # Same rule as the sidebar: module access, narrowed by any per-item role list.
        from apps.accounts.templatetags.navigation import NAV_ITEMS

        modules = MODULE_ACCESS.get(user.role, ["dashboard"])
        return [m for m in modules if user.role in NAV_ITEMS.get(m, {}).get("roles", [user.role])]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class SignupSerializer(serializers.Serializer):
    """Documents the signup payload; validation is done by accounts.forms.SignupForm."""
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=255)
    password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)


class VerifyOTPSerializer(serializers.Serializer):
    otp = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "Enter the 6-digit code."})


class ChangeRoleSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=UserRole.choices)


class RoleChoiceSerializer(serializers.Serializer):
    value = serializers.CharField()
    label = serializers.CharField()
