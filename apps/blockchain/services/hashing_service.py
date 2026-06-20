import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID


def _json_serializer(obj):
    """Custom JSON serializer for non-standard types."""
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, bytes):
        return obj.hex()
    raise TypeError(f"Type {type(obj)} is not JSON serializable")


def generate_file_hash(file_or_bytes):
    """
    Generate SHA-256 hash of a file.
    Accepts a Django FieldFile, file-like object, bytes, or file path string.
    """
    sha256 = hashlib.sha256()

    if isinstance(file_or_bytes, bytes):
        sha256.update(file_or_bytes)
    elif isinstance(file_or_bytes, str):
        # File path
        with open(file_or_bytes, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
    elif hasattr(file_or_bytes, "read"):
        # File-like object or Django FieldFile
        if hasattr(file_or_bytes, "seek"):
            file_or_bytes.seek(0)
        for chunk in iter(lambda: file_or_bytes.read(8192), b""):
            sha256.update(chunk)
        if hasattr(file_or_bytes, "seek"):
            file_or_bytes.seek(0)
    else:
        raise ValueError(f"Unsupported type for hashing: {type(file_or_bytes)}")

    return sha256.hexdigest()


def generate_data_hash(data_dict):
    """
    Generate SHA-256 hash of a dictionary by serializing to canonical JSON.
    """
    canonical = json.dumps(data_dict, sort_keys=True, default=_json_serializer)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compare_hashes(hash_a, hash_b):
    """Securely compare two hash strings."""
    if not hash_a or not hash_b:
        return False
    return hashlib.sha256(hash_a.encode()).digest() == hashlib.sha256(hash_b.encode()).digest()
