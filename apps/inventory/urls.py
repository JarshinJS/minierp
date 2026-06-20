from django.urls import path
from . import views

app_name = "inventory"

urlpatterns = [
	path("", views.InventoryHomeView.as_view(), name="home"),
	path("adjust/", views.InventoryAdjustView.as_view(), name="adjust"),
]
