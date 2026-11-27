"""
Secure access to stored trade documents.

Documents live in private storage (see settings STORAGES / docs/deployment.md) and
are never given a public URL. The only way to download one is

    GET /api/trade/documents/<id>/download/?token=<signed token>

which requires ALL of: an authenticated session of an approved user, a role in
roles.DOCUMENT_READ, and a token that was issued to *that user* for *that
document* and is younger than DOCUMENT_DOWNLOAD_URL_TTL seconds. Storage
credentials stay on the server; the browser only ever sees this API URL.
"""
import logging
import os
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.urls import reverse

from .validators import CONTENT_TYPES, safe_display_name

logger = logging.getLogger(__name__)

_SALT = "minierp.trade-document-download.v1"
DEFAULT_TTL_SECONDS = 300


class DownloadTokenError(Exception):
    """Raised for an invalid or expired download token. ``code`` says which."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def ttl_seconds():
    return int(getattr(settings, "DOCUMENT_DOWNLOAD_URL_TTL", DEFAULT_TTL_SECONDS))


def _payload(document_id, user_id):
    return f"{document_id}:{user_id}"


def make_download_token(document, user):
    return signing.TimestampSigner(salt=_SALT).sign(_payload(document.pk, user.pk))


def check_download_token(token, document_id, user):
    """Validate ``token`` for (document_id, user). Raises DownloadTokenError."""
    if not token:
        raise DownloadTokenError("download_link_invalid", "Download link is missing or invalid.")
    try:
        value = signing.TimestampSigner(salt=_SALT).unsign(token, max_age=ttl_seconds())
    except signing.SignatureExpired:
        raise DownloadTokenError("download_link_expired", "This download link has expired. Open the document again.")
    except signing.BadSignature:
        raise DownloadTokenError("download_link_invalid", "Download link is missing or invalid.")
    if value != _payload(document_id, user.pk):
        # Valid signature but for another document or another user.
        raise DownloadTokenError("download_link_invalid", "Download link is missing or invalid.")


def download_url(document, user):
    """Relative, signed, short-lived download URL for ``user`` (None for anonymous)."""
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    path = reverse("api:trade-document-download", args=[document.pk])
    return f"{path}?{urlencode({'token': make_download_token(document, user)})}"


def download_filename(document):
    """Filename offered to the browser: the sanitised original name, else title + extension."""
    ext = os.path.splitext(document.file.name or "")[1].lower()
    name = document.original_filename or f"{document.title}{ext}"
    name = safe_display_name(name)
    if ext and not name.lower().endswith(ext):
        name += ext  # never let the offered name change the file type
    return name


def content_type_for(document):
    """Served type is derived from the stored extension, never from the uploader."""
    ext = os.path.splitext(document.file.name or "")[1].lower()
    return CONTENT_TYPES.get(ext, "application/octet-stream")
