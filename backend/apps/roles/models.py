from django.db import models
from apps.core.models import TimeStampedModel
class Role(TimeStampedModel):
    customer = models.ForeignKey("customers.Customer", null=True, blank=True, on_delete=models.CASCADE, related_name="tenant_roles")
    name = models.CharField(max_length=100)
    slug = models.SlugField(db_index=True)
    description = models.TextField(blank=True)
    is_system_role = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    permissions = models.ManyToManyField("permissions.Permission", through="RolePermission", related_name="roles")
    class Meta:
        ordering = ("name",)
        constraints = [models.UniqueConstraint(fields=("customer", "slug"), name="unique_customer_role_slug")]
        indexes = [models.Index(fields=("customer", "is_active"))]
    def __str__(self): return self.name
class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="role_permissions")
    permission = models.ForeignKey("permissions.Permission", on_delete=models.CASCADE, related_name="role_permissions")
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta: constraints = [models.UniqueConstraint(fields=("role", "permission"), name="unique_role_permission")]
