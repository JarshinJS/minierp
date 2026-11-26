from django.db import connection
from django.http import JsonResponse

HEALTH_PATH = "/healthz/"


class HealthCheckMiddleware:
    """
    Answer the platform health probe before host validation and SSL redirects.

    Render's checker may use an internal Host header that isn't in ALLOWED_HOSTS,
    which Django would reject with a 400 and fail the deploy. The response has no
    details beyond ok/error, so skipping those checks here is safe. Must be first
    in MIDDLEWARE.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == HEALTH_PATH:
            try:
                connection.ensure_connection()
            except Exception:
                return JsonResponse({"status": "error"}, status=503)
            return JsonResponse({"status": "ok"})
        return self.get_response(request)
