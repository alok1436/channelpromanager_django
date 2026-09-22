from django.db import models

from apps.core.models import TimeStampedModel


def platform_logo_path(instance, filename):
    return f"platforms/{instance.code}/logo/{filename}"


class Platform(TimeStampedModel):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True)
    logo_url = models.URLField(max_length=500, blank=True)
    logo = models.ImageField(upload_to=platform_logo_path, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name
