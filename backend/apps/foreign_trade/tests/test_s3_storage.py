"""
Opt-in integration test of the private S3 storage path (Supabase Storage speaks the
same S3 API). Runs only when an S3-compatible test endpoint is configured, e.g. a
throwaway local MinIO:

    podman run -d --rm --name minio -p 127.0.0.1:9000:9000 \\
        -e MINIO_ROOT_USER=testkey -e MINIO_ROOT_PASSWORD=testsecret123 \\
        quay.io/minio/minio server /data
    S3_TEST_ENDPOINT_URL=http://127.0.0.1:9000 S3_TEST_ACCESS_KEY_ID=testkey \\
    S3_TEST_SECRET_ACCESS_KEY=testsecret123 pytest apps/foreign_trade/tests/test_s3_storage.py

Never point this at a production bucket: it creates and deletes objects.
"""
import hashlib
import os
import time
import uuid
from decimal import Decimal

import pytest
import requests
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import UserRole
from apps.foreign_trade.models import TradeDocument

ENDPOINT = os.getenv("S3_TEST_ENDPOINT_URL")
pytestmark = [
    pytest.mark.skipif(not ENDPOINT, reason="set S3_TEST_ENDPOINT_URL (+ keys) to run the S3 storage test"),
    pytest.mark.django_db,
]
User = get_user_model()
PDF = b"%PDF-1.7\nprivate trade document\n%%EOF\n"


@pytest.fixture
def s3_storage(settings):
    import boto3

    bucket = f"minierp-test-{uuid.uuid4().hex[:12]}"
    creds = {"aws_access_key_id": os.environ["S3_TEST_ACCESS_KEY_ID"],
             "aws_secret_access_key": os.environ["S3_TEST_SECRET_ACCESS_KEY"]}
    client = boto3.client("s3", endpoint_url=ENDPOINT, region_name="us-east-1", **creds)
    client.create_bucket(Bucket=bucket)  # private by default

    settings.STORAGE_BUCKET = bucket
    settings.STORAGES = {**settings.STORAGES, "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": bucket, "endpoint_url": ENDPOINT, "region_name": "us-east-1",
            "access_key": creds["aws_access_key_id"], "secret_key": creds["aws_secret_access_key"],
            "default_acl": None, "querystring_auth": True, "querystring_expire": 60,
            "file_overwrite": False, "addressing_style": "path", "signature_version": "s3v4",
        },
    }}
    settings.BLOCKCHAIN_MOCK_MODE = True
    yield client, bucket
    for obj in client.list_objects_v2(Bucket=bucket).get("Contents", []):
        client.delete_object(Bucket=bucket, Key=obj["Key"])
    client.delete_bucket(Bucket=bucket)


@pytest.fixture
def order(db):
    from apps.foreign_trade.models import Country, Currency, TradeCustomer
    from apps.foreign_trade.services import create_export_order

    owner = User.objects.create_user(email="o@s3.test", password="x-Pass-123", full_name="O", role=UserRole.TRADE_MANAGER)
    country = Country.objects.create(name="USA", code="US")
    currency = Currency.objects.create(code="USD", name="Dollar", symbol="$", exchange_rate=Decimal("1"))
    return create_export_order(customer=TradeCustomer.objects.create(name="C", country=country), country=country,
                               currency=currency, lines_data=[{"description": "x", "quantity": 1, "unit_price": Decimal("1")}],
                               created_by=owner)


def _client(role, email):
    user = User.objects.create_user(email=email, password="x-Pass-123", full_name=role, role=role)
    c = APIClient()
    c.force_login(user)
    return c


def test_private_bucket_round_trip(s3_storage, order):
    client, bucket = s3_storage
    writer = _client(UserRole.TRADE_MANAGER, "w@s3.test")
    response = writer.post(reverse("api:trade-document-list"), {
        "order_type": "export", "order_id": str(order.pk), "document_type": "BILL_OF_LADING", "title": "BoL",
        "file": SimpleUploadedFile("bol.pdf", PDF, content_type="application/pdf"),
    }, format="multipart")
    assert response.status_code == 201, response.content
    doc = TradeDocument.objects.get(pk=response.json()["id"])

    # The object is in the bucket under its random key...
    head = client.head_object(Bucket=bucket, Key=doc.file.name)
    assert head["ContentLength"] == len(PDF)
    # ...and is NOT publicly readable.
    public = requests.get(f"{ENDPOINT}/{bucket}/{doc.file.name}", timeout=10)
    assert public.status_code == 403

    # Authorised download through the API streams it from the bucket.
    reader = _client(UserRole.AUDITOR, "r@s3.test")
    link = reader.get(reverse("api:trade-document-detail", args=[doc.pk])).json()["file"]
    assert ENDPOINT not in link and bucket not in link  # storage location never exposed
    download = reader.get(link)
    assert download.status_code == 200
    assert b"".join(download.streaming_content) == PDF

    # The Celery worker path (hash the stored file) reads from the bucket too.
    from apps.blockchain.services.verification_service import register_document, verify_document

    bc = register_document(doc)
    assert bc.document_hash == hashlib.sha256(PDF).hexdigest()
    assert verify_document(doc)["verified"] is True

    # Uploads never overwrite: same name twice gives two distinct objects.
    second = writer.post(reverse("api:trade-document-list"), {
        "order_type": "export", "order_id": str(order.pk), "document_type": "BILL_OF_LADING", "title": "BoL",
        "file": SimpleUploadedFile("bol.pdf", PDF + b"v2", content_type="application/pdf"),
    }, format="multipart")
    assert TradeDocument.objects.get(pk=second.json()["id"]).file.name != doc.file.name


def test_storage_presigned_urls_are_short_lived(s3_storage, order):
    """Even URLs signed by the storage backend itself expire (the app never hands them out)."""
    client, bucket = s3_storage
    key = "trade_documents/TEST/expiry.pdf"
    client.put_object(Bucket=bucket, Key=key, Body=PDF)
    url = client.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=1)
    assert requests.get(url, timeout=10).status_code == 200
    time.sleep(2.5)
    assert requests.get(url, timeout=10).status_code == 403
