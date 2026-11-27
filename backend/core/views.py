from django.conf import settings
from django.http import HttpResponseNotFound, HttpResponseRedirect
from django.views import View


class FrontendPageView(View):
    """
    Placeholder for a page that has been rebuilt in the Next.js frontend.

    The URL name stays registered so remaining Django templates can keep linking
    to it with {% url %}. In production the Next.js app serves these paths before
    Django sees them; if the backend is hit directly, send the user to the
    frontend (FRONTEND_URL) instead.
    """

    def get(self, request, *args, **kwargs):
        frontend = getattr(settings, "FRONTEND_URL", "")
        if frontend:
            return HttpResponseRedirect(f"{frontend}{request.get_full_path()}")
        return HttpResponseNotFound("This page is served by the Next.js frontend.")
