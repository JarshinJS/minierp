"""
Private trade-document storage and access (Phase 0.6).

Before: files were stored under their original names and linked as /media/<path>
(no access control on the URL), and uploads were checked by extension only.
"""
import hashlib
import io
import re
import zipfile
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import AccountStatus, UserRole
from apps.foreign_trade import documents
from apps.foreign_trade.models import TradeDocument

User = get_user_model()
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def ooxml(folder="word/", macro=False):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr(f"{folder}document.xml", "<doc/>")
        if macro:
            z.writestr(f"{folder}vbaProject.bin", b"\x00macro")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    settings.BLOCKCHAIN_MOCK_MODE = True


def user(role, status=AccountStatus.APPROVED, email=None):
    return User.objects.create_user(email=email or f"{role.lower()}@docs.test", password="x-Pass-12345",
                                    full_name=role, role=role, account_status=status)


def client_for(u=None):
    c = APIClient()
    if u is not None:
        c.force_login(u)
    return c


@pytest.fixture
def order(db):
    from apps.foreign_trade.models import Country, Currency, Incoterm, TradeCustomer
    from apps.foreign_trade.services import create_export_order

    owner = user(UserRole.TRADE_MANAGER, email="owner@docs.test")
    country = Country.objects.create(name="USA", code="US")
    currency = Currency.objects.create(code="USD", name="US Dollar", symbol="$", exchange_rate=Decimal("1"))
    customer = TradeCustomer.objects.create(name="Importer", country=country)
    return create_export_order(customer=customer, country=country, currency=currency,
                               incoterm=Incoterm.objects.create(code="FOB", name="FOB"),
                               lines_data=[{"description": "x", "quantity": 1, "unit_price": Decimal("1")}],
                               created_by=owner)


def upload(client, order, name, content, content_type="application/pdf"):
    return client.post(reverse("api:trade-document-list"), {
        "order_type": "export", "order_id": str(order.pk), "document_type": "COMMERCIAL_INVOICE",
        "title": "Invoice", "file": SimpleUploadedFile(name, content, content_type=content_type),
    }, format="multipart")


@pytest.fixture
def doc(order):
    response = upload(client_for(user(UserRole.DOCUMENTATION_OFFICER)), order, "invoice-2026.pdf", PDF)
    assert response.status_code == 201, response.content
    return TradeDocument.objects.get(pk=response.json()["id"])


# --- uploads ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_upload_stores_under_random_key_and_returns_signed_link(order):
    response = upload(client_for(user(UserRole.TRADE_MANAGER)), order, "Q3 invoice.pdf", PDF)
    assert response.status_code == 201, response.content
    body = response.json()
    doc = TradeDocument.objects.get(pk=body["id"])

    assert re.fullmatch(r"trade_documents/COMMERCIAL_INVOICE/[0-9a-f]{32}\.pdf", doc.file.name)
    assert doc.original_filename == "Q3 invoice.pdf"
    assert body["original_filename"] == "Q3 invoice.pdf"
    assert "/media/" not in body["file"]
    url = urlparse(body["file"])
    assert url.path == reverse("api:trade-document-download", args=[doc.pk])
    assert parse_qs(url.query)["token"]


@pytest.mark.django_db
def test_path_traversal_filename_cannot_escape_storage(order, settings):
    response = upload(client_for(user(UserRole.TRADE_MANAGER)), order, "../../../../etc/cron.d/x.pdf", PDF)
    assert response.status_code == 201, response.content
    doc = TradeDocument.objects.get()
    assert ".." not in doc.file.name and doc.file.name.startswith("trade_documents/")
    assert doc.original_filename == "x.pdf"
    stored = settings.MEDIA_ROOT / doc.file.name
    assert stored.resolve().is_relative_to(settings.MEDIA_ROOT.resolve())


@pytest.mark.django_db
@pytest.mark.parametrize("name, content, content_type, message", [
    ("tool.exe", b"MZ\x90\x00", "application/octet-stream", "Unsupported file type"),
    ("page.html", b"<html><script>alert(1)</script>", "text/html", "Unsupported file type"),
    ("fake.pdf", b"<html><script>alert(1)</script>", "application/pdf", "contents do not match"),
    ("fake.pdf", PNG, "application/pdf", "contents do not match"),
    ("image.png", PDF, "image/png", "contents do not match"),
    ("invoice.pdf", PDF, "text/html", "does not match"),
    ("empty.pdf", b"", "application/pdf", "empty"),
    ("noext", PDF, "application/pdf", "Unsupported file type"),
    ("invoice.pdf.exe", PDF, "application/pdf", "Unsupported file type"),
    ("macro.docx", ooxml(macro=True), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "Macro"),
    ("notword.docx", ooxml(folder="evil/"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "valid Office"),
])
def test_invalid_uploads_rejected(order, name, content, content_type, message):
    response = upload(client_for(user(UserRole.TRADE_MANAGER)), order, name, content, content_type)
    assert response.status_code == 400, response.content
    assert message.lower() in str(response.json()).lower()
    assert TradeDocument.objects.count() == 0


def test_validator_rejects_control_characters_in_names():
    from django.core.exceptions import ValidationError
    from apps.foreign_trade.validators import validate_trade_document_file

    for name in ("bad\x00name.pdf", "bad\nname.pdf", "tab\tname.pdf"):
        with pytest.raises(ValidationError, match="Invalid file name"):
            validate_trade_document_file(SimpleUploadedFile(name, PDF, content_type="application/pdf"))


def test_display_names_are_capped_and_keep_extension():
    from apps.foreign_trade.validators import safe_display_name

    name = safe_display_name("x" * 400 + ".pdf")
    assert len(name) <= 200 and name.endswith(".pdf")
    assert safe_display_name("..\\..\\windows\\evil.pdf") == "evil.pdf"
    assert safe_display_name("") == "document"


@pytest.mark.django_db
def test_control_characters_never_reach_stored_names(order):
    """Django's multipart parser already strips NULs; whatever arrives is stored safely."""
    upload(client_for(user(UserRole.TRADE_MANAGER)), order, "bad\x00na\rme.pdf", PDF)
    for doc in TradeDocument.objects.all():
        assert not any(ord(c) < 32 for c in doc.original_filename + doc.file.name)


@pytest.mark.django_db
def test_oversized_upload_rejected(order):
    big = PDF + b"0" * (10 * 1024 * 1024)
    response = upload(client_for(user(UserRole.TRADE_MANAGER)), order, "big.pdf", big)
    assert response.status_code == 400
    assert "too large" in str(response.json())


@pytest.mark.django_db
@pytest.mark.parametrize("name, content, ctype", [
    ("scan.png", PNG, "image/png"),
    ("scan.jpg", b"\xff\xd8\xff\xe0" + b"\x00" * 16, "image/jpeg"),
    ("letter.docx", ooxml("word/"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("sheet.xlsx", ooxml("xl/"), "application/octet-stream"),  # generic type: bytes decide
    ("legacy.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 16, "application/msword"),
])
def test_valid_types_accepted(order, name, content, ctype):
    assert upload(client_for(user(UserRole.TRADE_MANAGER)), order, name, content, ctype).status_code == 201


@pytest.mark.django_db
@pytest.mark.parametrize("role", [UserRole.AUDITOR, UserRole.FINANCE_MANAGER, UserRole.SALES_USER])
def test_upload_requires_document_write_role(order, role):
    assert upload(client_for(user(role)), order, "a.pdf", PDF).status_code == 403


@pytest.mark.django_db
def test_upload_refused_for_pending_and_anonymous(order):
    assert upload(client_for(user(UserRole.ADMIN, AccountStatus.PENDING)), order, "a.pdf", PDF).status_code == 403
    assert upload(client_for(), order, "a.pdf", PDF).status_code in (401, 403)


# --- downloads -------------------------------------------------------------------------

@pytest.mark.django_db
def test_authorized_download(doc):
    reader = user(UserRole.AUDITOR)
    client = client_for(reader)
    link = client.get(reverse("api:trade-document-detail", args=[doc.pk])).json()["file"]
    response = client.get(link)
    assert response.status_code == 200
    assert b"".join(response.streaming_content) == PDF
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"].startswith("attachment;")
    assert 'filename="invoice-2026.pdf"' in response["Content-Disposition"]
    assert response["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in response["Cache-Control"]
    assert "sandbox" in response["Content-Security-Policy"]


@pytest.mark.django_db
def test_download_requires_login_and_role(doc):
    reader = user(UserRole.AUDITOR)
    link = documents.download_url(doc, reader)
    assert client_for().get(link).status_code in (401, 403)
    for role in (UserRole.SALES_USER, UserRole.FINANCE_MANAGER, UserRole.ACCOUNTANT):
        other = user(role)
        assert client_for(other).get(documents.download_url(doc, other)).status_code == 403, role


@pytest.mark.django_db
def test_download_refused_for_suspended_user(doc):
    reader = user(UserRole.AUDITOR)
    link = documents.download_url(doc, reader)
    client = client_for(reader)
    User.objects.filter(pk=reader.pk).update(account_status=AccountStatus.SUSPENDED)
    assert client.get(link).status_code == 403


@pytest.mark.django_db
def test_link_is_bound_to_user_and_document(doc, order):
    alice, bob = user(UserRole.AUDITOR, email="a@docs.test"), user(UserRole.AUDITOR, email="b@docs.test")
    writer = user(UserRole.TRADE_MANAGER, email="w@docs.test")
    other = TradeDocument.objects.get(pk=upload(client_for(writer), order, "b.pdf", PDF).json()["id"])

    alices_link = documents.download_url(doc, alice)
    # Bob is allowed to read documents, but not with Alice's link (cross-user).
    response = client_for(bob).get(alices_link)
    assert response.status_code == 403 and response.json()["code"] == "download_link_invalid"
    # A valid token for doc A doesn't open doc B.
    token = parse_qs(urlparse(alices_link).query)["token"][0]
    url = reverse("api:trade-document-download", args=[other.pk]) + f"?token={token}"
    assert client_for(alice).get(url).status_code == 403


@pytest.mark.django_db
def test_missing_and_tampered_tokens(doc):
    reader = user(UserRole.AUDITOR)
    client = client_for(reader)
    base = reverse("api:trade-document-download", args=[doc.pk])
    assert client.get(base).status_code == 403
    good = documents.make_download_token(doc, reader)
    for bad in (good[:-1] + ("A" if good[-1] != "A" else "B"), "garbage", f"{doc.pk}:{reader.pk}"):
        response = client.get(base, {"token": bad})
        assert response.status_code == 403 and response.json()["code"] == "download_link_invalid"


@pytest.mark.django_db
def test_expired_link(doc, monkeypatch):
    import time as real_time

    reader = user(UserRole.AUDITOR)
    link = documents.download_url(doc, reader)

    class Later:
        @staticmethod
        def time():
            return real_time.time() + documents.ttl_seconds() + 5

    monkeypatch.setattr("django.core.signing.time", Later)
    response = client_for(reader).get(link)
    assert response.status_code == 403
    assert response.json()["code"] == "download_link_expired"


@pytest.mark.django_db
def test_no_enumeration_without_valid_token():
    import uuid

    reader = user(UserRole.AUDITOR)
    missing = uuid.uuid4()
    url = reverse("api:trade-document-download", args=[missing])
    # Bad token: same 403 whether or not the document exists.
    assert client_for(reader).get(url, {"token": "x"}).status_code == 403


@pytest.mark.django_db
def test_missing_stored_file_is_404(doc):
    reader = user(UserRole.AUDITOR)
    doc.file.storage.delete(doc.file.name)
    assert client_for(reader).get(documents.download_url(doc, reader)).status_code == 404


@pytest.mark.django_db
def test_media_is_never_served(doc):
    admin = user(UserRole.ADMIN)
    for client in (client_for(), client_for(admin)):
        response = client.get(f"/media/{doc.file.name}")
        assert response.status_code in (302, 404)
        assert b"%PDF" not in response.content


@pytest.mark.django_db
def test_html_pages_link_to_signed_download_not_media(doc, order):
    page = client_for(user(UserRole.ADMIN)).get(
        reverse("foreign_trade:document_history", args=["export", order.pk]), {"document_type": "COMMERCIAL_INVOICE"}
    ).content.decode()
    assert "/media/" not in page
    assert reverse("api:trade-document-download", args=[doc.pk]) + "?token=" in page


@pytest.mark.django_db
def test_offered_filename_keeps_stored_type(doc):
    TradeDocument.objects.filter(pk=doc.pk).update(original_filename="invoice.html")
    doc.refresh_from_db()
    assert documents.download_filename(doc).endswith(".pdf")
    assert documents.content_type_for(doc) == "application/pdf"


# --- blockchain integrity is unaffected ---------------------------------------------------

@pytest.mark.django_db
def test_upload_then_anchor_and_verify(doc):
    from apps.blockchain.services.verification_service import register_document, verify_document

    bc = register_document(doc)
    assert bc.document_hash == hashlib.sha256(PDF).hexdigest()
    assert verify_document(doc)["verified"] is True


# --- storage migration ---------------------------------------------------------------------

@pytest.mark.django_db
def test_migration_command_copies_keys_unchanged_and_verifies(doc, settings, tmp_path):
    from apps.blockchain.services.verification_service import register_document

    register_document(doc)
    local_root = settings.MEDIA_ROOT
    name = doc.file.name

    with pytest.raises(CommandError, match="STORAGE_BUCKET"):
        call_command("migrate_trade_documents_to_storage", source=str(local_root))

    # Stand-in for the bucket: another directory behind the default storage.
    settings.STORAGE_BUCKET = "private-test-bucket"
    settings.STORAGES = {**settings.STORAGES, "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": str(tmp_path / "bucket")},
    }}
    out = io.StringIO()
    call_command("migrate_trade_documents_to_storage", source=str(local_root), dry_run=True, stdout=out)
    assert "would copy: 1" in out.getvalue()
    assert not (tmp_path / "bucket" / name).exists()

    call_command("migrate_trade_documents_to_storage", source=str(local_root), stdout=io.StringIO())
    assert (tmp_path / "bucket" / name).read_bytes() == PDF  # same key, same bytes
    doc.refresh_from_db()
    assert doc.file.name == name

    out = io.StringIO()
    call_command("migrate_trade_documents_to_storage", source=str(local_root), stdout=out)  # idempotent
    assert "copied: 0, already in storage: 1" in out.getvalue()


@pytest.mark.django_db
def test_migration_command_reports_files_altered_after_anchoring(doc, settings, tmp_path):
    from apps.blockchain.services.verification_service import register_document

    register_document(doc)
    (settings.MEDIA_ROOT / doc.file.name).write_bytes(PDF + b"tampered")
    settings.STORAGE_BUCKET = "private-test-bucket"
    settings.STORAGES = {**settings.STORAGES, "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": str(tmp_path / "bucket")},
    }}
    err = io.StringIO()
    call_command("migrate_trade_documents_to_storage", source=str(settings.MEDIA_ROOT), stdout=io.StringIO(), stderr=err)
    assert "TAMPERED" in err.getvalue()
