"""
Upload validation for trade documents (used by the HTML form and the REST API).

A file is accepted only if ALL of these agree:
  * the extension is on the allowlist;
  * the file's first bytes match that type (magic-number sniffing, so a renamed
    executable or HTML page is rejected);
  * the browser-declared MIME type, when given, fits the extension;
  * the size is between 1 byte and MAX_DOCUMENT_SIZE;
  * the filename is a plain, printable name (no paths, control characters...).

Files are stored under a random name (see models.trade_document_upload_path), so
the original filename never becomes a storage path.
"""
import os
import unicodedata
import zipfile

from django.core.exceptions import ValidationError

MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_FILENAME_LENGTH = 200

_OLE2 = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"   # legacy .doc / .xls
_ZIP = b"PK\x03\x04"                            # .docx / .xlsx containers

# extension -> (magic prefixes, accepted MIME types, OOXML part folder or None)
DOCUMENT_TYPES = {
    ".pdf": ((b"%PDF-",), {"application/pdf"}, None),
    ".png": ((b"\x89PNG\r\n\x1a\n",), {"image/png"}, None),
    ".jpg": ((b"\xff\xd8\xff",), {"image/jpeg", "image/pjpeg"}, None),
    ".jpeg": ((b"\xff\xd8\xff",), {"image/jpeg", "image/pjpeg"}, None),
    ".doc": ((_OLE2,), {"application/msword"}, None),
    ".xls": ((_OLE2,), {"application/vnd.ms-excel"}, None),
    ".docx": ((_ZIP,), {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}, "word/"),
    ".xlsx": ((_ZIP,), {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}, "xl/"),
}
ALLOWED_DOCUMENT_EXTENSIONS = set(DOCUMENT_TYPES)
# What the stored file is served as (never the client-declared type).
CONTENT_TYPES = {ext: sorted(mimes)[0] for ext, (_, mimes, _) in DOCUMENT_TYPES.items()}
CONTENT_TYPES[".jpg"] = CONTENT_TYPES[".jpeg"] = "image/jpeg"
# Browsers/clients send these when they don't know the type; the bytes decide.
_GENERIC_MIME = {"", "application/octet-stream", "binary/octet-stream"}


def safe_display_name(name):
    """
    The original filename reduced to a safe display name: last path component
    only (both / and \\), Unicode-normalised, without control characters, and
    length-limited. Used for Content-Disposition, never as a storage path.
    """
    name = unicodedata.normalize("NFC", str(name or ""))
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if unicodedata.category(ch)[0] != "C").strip().strip(".")
    if not name:
        return "document"
    stem, ext = os.path.splitext(name)
    return stem[: MAX_FILENAME_LENGTH - len(ext)] + ext


def _read_head(file, size=16):
    if hasattr(file, "seek"):
        file.seek(0)
    head = file.read(size)
    if hasattr(file, "seek"):
        file.seek(0)
    return head or b""


def _check_ooxml(file, folder):
    """A real .docx/.xlsx: a zip with the OOXML manifest and the right part folder, no macros."""
    try:
        file.seek(0)
        with zipfile.ZipFile(file) as archive:
            names = archive.namelist()
    except (zipfile.BadZipFile, OSError, ValueError):
        raise ValidationError("The file is not a valid Office document.")
    finally:
        file.seek(0)
    if "[Content_Types].xml" not in names or not any(n.startswith(folder) for n in names):
        raise ValidationError("The file is not a valid Office document.")
    if any(n.lower().endswith("vbaproject.bin") for n in names):
        raise ValidationError("Macro-enabled Office documents are not allowed.")


def validate_trade_document_file(file):
    """Server-side check for uploaded trade documents. Returns the file or raises ValidationError."""
    raw_name = str(getattr(file, "name", "") or "")
    if not raw_name or len(raw_name) > 255 or any(unicodedata.category(c) == "Cc" for c in raw_name):
        raise ValidationError("Invalid file name.")
    ext = os.path.splitext(safe_display_name(raw_name))[1].lower()
    if ext not in DOCUMENT_TYPES:
        raise ValidationError(
            f"Unsupported file type '{ext or 'none'}'. Allowed: {', '.join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))}."
        )

    size = getattr(file, "size", None)
    if not size:
        raise ValidationError("The file is empty.")
    if size > MAX_DOCUMENT_SIZE:
        raise ValidationError(f"File is too large (max {MAX_DOCUMENT_SIZE // (1024 * 1024)} MB).")

    magics, mimes, ooxml_folder = DOCUMENT_TYPES[ext]
    declared = (getattr(file, "content_type", "") or "").split(";")[0].strip().lower()
    if declared not in _GENERIC_MIME and declared not in mimes:
        raise ValidationError(f"The file's type ({declared}) does not match its '{ext}' extension.")

    head = _read_head(file)
    if not any(head.startswith(m) for m in magics):
        raise ValidationError(f"The file's contents do not match its '{ext}' extension.")
    if ooxml_folder:
        _check_ooxml(file, ooxml_folder)
    return file
