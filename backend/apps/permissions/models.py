from django.db import models
from apps.core.models import TimeStampedModel
class Permission(TimeStampedModel):
    module = models.ForeignKey("modules.Module", on_delete=models.PROTECT, related_name="permissions")
    name = models.CharField(max_length=150)
    codename = models.CharField(max_length=150, unique=True, db_index=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    class Meta: ordering = ("module__sort_order", "codename")
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.module_id and not self.codename.startswith(f"{self.module.slug}."):
            raise ValidationError({"codename": "Codename must start with the module slug."})
    def __str__(self): return self.codename
