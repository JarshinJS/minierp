import os

from django.core.exceptions import ValidationError

ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".xlsx", ".xls"}
MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10 MB


def validate_trade_document_file(file):
    """Server-side check for uploaded trade documents (type by extension, and size)."""
    ext = os.path.splitext(file.name or "")[1].lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValidationError(
            f"Unsupported file type '{ext or 'none'}'. Allowed: {', '.join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))}."
        )
    if file.size > MAX_DOCUMENT_SIZE:
        raise ValidationError(f"File is too large (max {MAX_DOCUMENT_SIZE // (1024 * 1024)} MB).")
    return file
