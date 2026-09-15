from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


def company_logo_path(instance, filename):
    return f"companies/customer_{instance.customer_id}/{filename}"


class Company(TimeStampedModel):
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="companies",
    )
    name = models.CharField(max_length=255)
    street_1 = models.CharField(max_length=255, blank=True)
    street_2 = models.CharField(max_length=255, blank=True)
    postal_code = models.CharField(max_length=30, blank=True, db_index=True)
    city = models.CharField(max_length=100, blank=True, db_index=True)
    province = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True, db_index=True)
    phone = models.CharField(max_length=50, blank=True)
    fax = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    logo = models.FileField(upload_to=company_logo_path, null=True, blank=True)
    note = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("customer", "name"),
                condition=Q(is_active=True),
                name="unique_active_company_name_per_customer",
            )
        ]
        indexes = [models.Index(fields=("customer", "is_active"))]

    def __str__(self):
        return self.name
