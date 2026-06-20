from django.db import models
from core.models import UUIDBaseModel, TimeStampedModel

class Vendor(UUIDBaseModel, TimeStampedModel):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    contact_name = models.CharField(max_length=255, blank=True)
    email = models.EmailField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})"
