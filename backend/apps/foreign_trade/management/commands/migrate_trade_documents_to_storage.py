"""
Copy existing trade-document files from local disk into the configured private
object storage, keeping each file's key (TradeDocument.file.name) unchanged so no
database reference changes.

    python manage.py migrate_trade_documents_to_storage --dry-run
    python manage.py migrate_trade_documents_to_storage [--source /path/to/media]

* Idempotent: objects already present in the bucket are verified, not re-uploaded.
* Every copy is verified by SHA-256 against the local bytes, and against the hash
  anchored on the blockchain (BlockchainDocument.document_hash) when there is one.
  A mismatch with the anchored hash is reported (the file was altered after it was
  anchored) but the bytes are still copied as-is: nothing is "fixed" silently.
* Never deletes local files. Remove them yourself once the report is clean.
"""
import hashlib

from django.conf import settings
from django.core.files.base import File
from django.core.files.storage import FileSystemStorage, default_storage
from django.core.management.base import BaseCommand, CommandError

from apps.foreign_trade.models import TradeDocument


def _sha256(fh):
    digest = hashlib.sha256()
    for chunk in iter(lambda: fh.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


class Command(BaseCommand):
    help = "Copy trade documents from local MEDIA_ROOT into the private object storage (keys unchanged)."

    def add_arguments(self, parser):
        parser.add_argument("--source", default=str(settings.MEDIA_ROOT), help="Local media directory (default MEDIA_ROOT)")
        parser.add_argument("--dry-run", action="store_true", help="Report only; upload nothing")

    def handle(self, *args, source, dry_run, **options):
        if not getattr(settings, "STORAGE_BUCKET", ""):
            raise CommandError("The default storage is local disk. Set STORAGE_BUCKET (and credentials) first.")
        local = FileSystemStorage(location=source)
        stats = {"copied": 0, "present": 0, "missing_locally": 0, "anchored_mismatch": 0, "copy_mismatch": 0}

        for doc in TradeDocument.objects.order_by("created_at").iterator():
            name = doc.file.name
            if not name:
                continue
            anchored = (doc.blockchain_records.order_by("-created_at")
                        .values_list("document_hash", flat=True).first())

            if not local.exists(name):
                if default_storage.exists(name):
                    stats["present"] += 1
                else:
                    stats["missing_locally"] += 1
                    self.stderr.write(f"MISSING  {doc.pk} {name}: not on local disk nor in storage")
                continue

            with local.open(name, "rb") as fh:
                local_hash = _sha256(fh)
            if anchored and anchored != local_hash:
                stats["anchored_mismatch"] += 1
                self.stderr.write(f"TAMPERED {doc.pk} {name}: local file does not match its anchored hash")

            if default_storage.exists(name):
                with default_storage.open(name, "rb") as fh:
                    remote_hash = _sha256(fh)
                if remote_hash != local_hash:
                    stats["copy_mismatch"] += 1
                    self.stderr.write(f"DIFFERS  {doc.pk} {name}: object in storage differs from local file")
                else:
                    stats["present"] += 1
                continue

            if dry_run:
                self.stdout.write(f"would copy {name}")
                stats["copied"] += 1
                continue
            with local.open(name, "rb") as fh:
                saved = default_storage.save(name, File(fh, name=name))
            if saved != name:
                raise CommandError(f"Storage renamed {name} to {saved}; aborting so references stay valid.")
            with default_storage.open(name, "rb") as fh:
                if _sha256(fh) != local_hash:
                    stats["copy_mismatch"] += 1
                    self.stderr.write(f"DIFFERS  {doc.pk} {name}: verification after upload failed")
                    continue
            stats["copied"] += 1
            self.stdout.write(f"copied   {name}")

        verb = "would copy" if dry_run else "copied"
        self.stdout.write(
            f"{verb}: {stats['copied']}, already in storage: {stats['present']}, "
            f"missing: {stats['missing_locally']}, anchored-hash mismatches: {stats['anchored_mismatch']}, "
            f"copy mismatches: {stats['copy_mismatch']}"
        )
        if stats["copy_mismatch"] or stats["missing_locally"]:
            raise CommandError("Migration finished with problems; see messages above.")
