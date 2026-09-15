from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


class Warehouse(TimeStampedModel):
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="warehouses",
    )
    company = models.ForeignKey(
        "companies.Company",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="warehouses",
    )
    name = models.CharField(max_length=255)
    street1 = models.CharField(max_length=255, blank=True)
    street2 = models.CharField(max_length=255, blank=True)
    plz = models.CharField(max_length=30, blank=True, db_index=True)
    city = models.CharField(max_length=100, blank=True, db_index=True)
    province = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True, db_index=True)
    phone = models.CharField(max_length=50, blank=True)
    fax = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("customer", "name"),
                name="unique_warehouse_name_per_customer",
            )
        ]
        indexes = [models.Index(fields=("customer", "name"), name="warehouses_customer_name_idx")]

    def __str__(self):
        return self.name
