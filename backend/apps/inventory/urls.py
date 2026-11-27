"""
urls.py for the Inventory app.

The inventory page is served by the Next.js frontend (data from /api/inventory/).
The name stays registered so the remaining Django templates can link to it.
"""
from django.urls import path

from core.views import FrontendPageView

app_name = "inventory"

urlpatterns = [
    path("", FrontendPageView.as_view(), name="home"),
]
