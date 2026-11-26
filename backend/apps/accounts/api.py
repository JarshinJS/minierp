"""
REST API for authentication and user management.

Auth uses Django sessions + CSRF, so the frontend must:
  1. GET  /api/auth/csrf/   once, to receive the ``csrftoken`` cookie;
  2. send it back in the ``X-CSRFToken`` header on every unsafe request.
"""
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.db.models import Q
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.exceptions import DomainError
from . import services, signup
from .forms import SignupForm
from .models import UserRole
from .permissions import DRFRolePermission, roles_for_module
from .serializers import (
    ChangeRoleSerializer, CurrentUserSerializer, LoginSerializer, RoleChoiceSerializer,
    SignupSerializer, UserSerializer, VerifyOTPSerializer,
)

User = get_user_model()

DetailSerializer = inline_serializer("Detail", {"detail": serializers.CharField()})
SignupErrorSerializer = inline_serializer(
    "SignupError", {"detail": serializers.CharField(), "restart": serializers.BooleanField()}
)


def _signup_error_response(error):
    body = {"detail": error.message, "restart": error.restart}
    if error.field:
        body = {error.field: [error.message], **body}
    return Response(body, status=status.HTTP_400_BAD_REQUEST)


class _PublicAuthView(APIView):
    """
    Unauthenticated auth endpoints. DRF skips CSRF for anonymous requests, so it
    is enforced explicitly (prevents login-CSRF). Throttled per client IP.
    """
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    @method_decorator(csrf_protect)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)


class CSRFTokenAPIView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses=inline_serializer("CSRFToken", {"csrfToken": serializers.CharField()}))
    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        """Set the CSRF cookie and return the token."""
        return Response({"csrfToken": get_token(request)})


class LoginAPIView(_PublicAuthView):
    @extend_schema(request=LoginSerializer, responses={200: CurrentUserSerializer, 400: DetailSerializer})
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        # authenticate() returns None for inactive users too; don't reveal which.
        if user is None:
            return Response({"detail": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST)
        auth_login(request, user)
        return Response(CurrentUserSerializer(user).data)


class LogoutAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        auth_logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserAPIView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses=CurrentUserSerializer)
    def get(self, request):
        return Response(CurrentUserSerializer(request.user).data)


class SignupAPIView(_PublicAuthView):
    @extend_schema(
        request=SignupSerializer,
        responses={202: inline_serializer("SignupStarted", {
            "detail": serializers.CharField(), "email": serializers.EmailField(),
            "expires_in": serializers.IntegerField(),
        }), 400: SignupErrorSerializer},
    )
    def post(self, request):
        """Start signup: validates the details and emails a 6-digit code."""
        form = SignupForm(data=request.data)
        if not form.is_valid():
            errors = {
                ("non_field_errors" if field == "__all__" else field): [str(e) for e in errs]
                for field, errs in form.errors.items()
            }
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            signup.start_signup(
                request.session,
                email=form.cleaned_data["email"],
                full_name=form.cleaned_data["full_name"],
                password=form.cleaned_data["password"],
            )
        except signup.SignupError as e:
            return _signup_error_response(e)
        return Response(
            {"detail": "Verification code sent.", "email": form.cleaned_data["email"],
             "expires_in": signup.OTP_TTL_SECONDS},
            status=status.HTTP_202_ACCEPTED,
        )


class SignupVerifyAPIView(_PublicAuthView):
    @extend_schema(request=VerifyOTPSerializer, responses={201: UserSerializer, 400: SignupErrorSerializer})
    def post(self, request):
        """Verify the emailed code and create the account (the user then logs in)."""
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            user = signup.verify_signup(request.session, serializer.validated_data["otp"])
        except signup.SignupError as e:
            return _signup_error_response(e)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class SignupResendAPIView(_PublicAuthView):
    @extend_schema(request=None, responses={200: DetailSerializer, 400: SignupErrorSerializer})
    def post(self, request):
        try:
            signup.resend_otp(request.session)
        except signup.SignupError as e:
            return _signup_error_response(e)
        return Response({"detail": "A new verification code was sent."})


@extend_schema(parameters=[
    OpenApiParameter("search", str, description="Matches email or full name"),
    OpenApiParameter("role", str, enum=UserRole.values),
    OpenApiParameter("is_active", bool),
])
class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """User administration (Admin / Business Owner)."""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, DRFRolePermission]
    allowed_roles = roles_for_module("accounts")

    def get_queryset(self):
        qs = User.objects.all().order_by("email")
        params = self.request.query_params
        if search := params.get("search", "").strip():
            qs = qs.filter(Q(email__icontains=search) | Q(full_name__icontains=search))
        if (role := params.get("role")) in UserRole.values:
            qs = qs.filter(role=role)
        if (active := params.get("is_active")) in ("true", "false"):
            qs = qs.filter(is_active=active == "true")
        return qs

    def _get_other_user(self, request):
        user = self.get_object()
        if user == request.user:
            raise DomainError("You cannot change your own account here.")
        return user

    @extend_schema(request=None, responses=UserSerializer)
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = services.activate_user(self._get_other_user(request))
        return Response(UserSerializer(user).data)

    @extend_schema(request=None, responses=UserSerializer)
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = services.deactivate_user(self._get_other_user(request))
        return Response(UserSerializer(user).data)

    @extend_schema(request=ChangeRoleSerializer, responses=UserSerializer)
    @action(detail=True, methods=["post"], url_path="change-role")
    def change_role(self, request, pk=None):
        user = self._get_other_user(request)
        serializer = ChangeRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.change_role(user, serializer.validated_data["role"])
        return Response(UserSerializer(user).data)

    @extend_schema(responses=RoleChoiceSerializer(many=True))
    @action(detail=False, methods=["get"], pagination_class=None)
    def roles(self, request):
        return Response([{"value": v, "label": l} for v, l in UserRole.choices])
