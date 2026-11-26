"""
Shared REST API plumbing: exception handling and a CSV renderer.
"""
import csv
import io

from rest_framework import status
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from core.exceptions import DomainError


def exception_handler(exc, context):
    """
    DRF exception handler that turns business-rule violations (DomainError and
    subclasses such as WorkflowError / InsufficientStockError) into 400s with a
    ``{"detail": ...}`` body, matching DRF's own error shape.
    """
    if isinstance(exc, DomainError):
        return Response({"detail": exc.message}, status=status.HTTP_400_BAD_REQUEST)
    return drf_exception_handler(exc, context)


class CSVRenderer(BaseRenderer):
    """
    Renders ``{"columns": [...], "rows": [[...], ...]}`` as CSV.
    Selected with ``?format=csv`` on views that list it in ``renderer_classes``.
    """
    media_type = "text/csv"
    format = "csv"
    charset = "utf-8"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if not isinstance(data, dict) or "rows" not in data:
            # Errors (e.g. {"detail": ...}) still render as a one-cell CSV.
            data = {"columns": ["detail"], "rows": [[data.get("detail", "") if isinstance(data, dict) else data]]}
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(data.get("columns", []))
        writer.writerows(data["rows"])
        return buffer.getvalue().encode(self.charset)


def api_paths_only(endpoints, **kwargs):
    """drf-spectacular preprocessing hook: document only the /api/ endpoints."""
    return [endpoint for endpoint in endpoints if endpoint[0].startswith("/api/")]
