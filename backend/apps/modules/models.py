from django.db import models
from apps.core.models import TimeStampedModel
class Module(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, db_index=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    deleted_at = models.DateTimeField(null=True, blank=True)
    class Meta: ordering = ("sort_order", "name")
    def __str__(self): return self.name
