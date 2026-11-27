"""
Email-OTP signup flow, shared by the HTML views and the REST API.

State lives in the user's session under ``SESSION_KEY`` until the OTP is
verified. Only the password *hash* is stored, never the raw password.
Self-registered accounts are created PENDING: they cannot use the ERP until an
administrator approves them and picks their role (services.approve_user). Only
email, full name and password are read from the request, so a signup payload
can't set its own role, status or staff flags.
"""
import hmac
import logging
import secrets
import time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail

from core.exceptions import DomainError
from . import services
from .models import AccountStatus

logger = logging.getLogger(__name__)
User = get_user_model()

SESSION_KEY = "signup_data"
OTP_TTL_SECONDS = 300
OTP_MAX_ATTEMPTS = 5
OTP_RESEND_COOLDOWN_SECONDS = 30
OTP_MAX_RESENDS = 5


class SignupError(DomainError):
    """
    A signup step failed. ``field`` names the input at fault (or None for a
    general error); ``restart`` means the pending signup was discarded and the
    user must start again.
    """
    def __init__(self, message, field=None, restart=False):
        super().__init__(message)
        self.field = field
        self.restart = restart


def _generate_otp():
    return f"{secrets.randbelow(1_000_000):06d}"


def _send_otp(email, otp):
    """Email the OTP. The code itself is never written to logs."""
    try:
        send_mail(
            subject="Your verification code",
            message=f"Your verification code is {otp}. It expires in {OTP_TTL_SECONDS // 60} minutes.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )
    except Exception as exc:
        logger.exception("Failed to send signup OTP email")
        raise SignupError("We couldn't send the verification email. Please try again later.") from exc


def pending_signup(session):
    """Return the pending signup dict, or None."""
    return session.get(SESSION_KEY)


def start_signup(session, email, full_name, password):
    """Validate uniqueness, email an OTP and store the pending signup in the session."""
    if User.objects.filter(email__iexact=email).exists():
        raise SignupError(f"A user with email '{email}' already exists.", field="email")

    otp = _generate_otp()
    _send_otp(email, otp)
    now = time.time()
    session[SESSION_KEY] = {
        "email": email,
        "password_hash": make_password(password),
        "full_name": full_name,
        "otp": otp,
        "otp_expiry": now + OTP_TTL_SECONDS,
        "otp_sent_at": now,
        "attempts": 0,
        "resends": 0,
    }


def verify_signup(session, otp):
    """Check the OTP and create the user. Returns the new user."""
    data = session.get(SESSION_KEY)
    if not data:
        raise SignupError("No signup in progress. Please sign up again.", restart=True)

    # Count every guess before checking it, so the limit can't be raced.
    data["attempts"] = data.get("attempts", 0) + 1
    session[SESSION_KEY] = data
    if data["attempts"] > OTP_MAX_ATTEMPTS:
        del session[SESSION_KEY]
        raise SignupError("Too many incorrect codes. Please sign up again.", restart=True)

    if time.time() > data.get("otp_expiry", 0):
        raise SignupError("The OTP has expired. Please request a new one.", field="otp")

    if not hmac.compare_digest(str(otp), str(data.get("otp", ""))):
        raise SignupError("Invalid OTP. Please try again.", field="otp")

    user = services.create_user(
        email=data["email"],
        password=None,
        password_hash=data["password_hash"],
        full_name=data["full_name"],
        account_status=AccountStatus.PENDING,
    )
    del session[SESSION_KEY]
    return user


def resend_otp(session):
    """Email a fresh OTP, subject to a cooldown and a resend limit."""
    data = session.get(SESSION_KEY)
    if not data:
        raise SignupError("No signup in progress. Please sign up again.", restart=True)

    if time.time() - data.get("otp_sent_at", 0) < OTP_RESEND_COOLDOWN_SECONDS:
        raise SignupError(f"Please wait {OTP_RESEND_COOLDOWN_SECONDS} seconds before requesting another code.")
    if data.get("resends", 0) >= OTP_MAX_RESENDS:
        del session[SESSION_KEY]
        raise SignupError("Too many codes requested. Please sign up again.", restart=True)

    otp = _generate_otp()
    _send_otp(data["email"], otp)
    now = time.time()
    data.update({
        "otp": otp,
        "otp_expiry": now + OTP_TTL_SECONDS,
        "otp_sent_at": now,
        "attempts": 0,
        "resends": data.get("resends", 0) + 1,
    })
    session[SESSION_KEY] = data
