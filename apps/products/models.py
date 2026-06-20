from django.db import models

from core.models import UUIDBaseModel, TimeStampedModel


class Product(UUIDBaseModel, TimeStampedModel):
	name = models.CharField(max_length=255)
	on_hand_qty = models.DecimalField(max_digits=12, decimal_places=2, default=0)

	def __str__(self):
		return self.name
