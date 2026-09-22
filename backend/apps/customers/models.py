from django.conf import settings
from django.db import models
from apps.core.models import TimeStampedModel
class Customer(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="customer")
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    company = models.CharField(max_length=255, blank=True, db_index=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(unique=True, db_index=True)
    address = models.TextField(blank=True)
    open_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    product_languages = models.JSONField(default=list, blank=True)
    def __str__(self): return f"{self.first_name} {self.last_name}"

    @property
    def company_name(self):
        return self.company

class CustomerMembership(TimeStampedModel):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="customer_memberships")
    role = models.ForeignKey("roles.Role", null=True, blank=True, on_delete=models.PROTECT, related_name="memberships")
    is_owner = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("customer", "user"), name="unique_customer_user_membership"),
            models.UniqueConstraint(fields=("customer",), condition=models.Q(is_owner=True, is_active=True), name="unique_active_owner_per_customer"),
        ]
        indexes = [models.Index(fields=("user", "is_active"))]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.role_id and self.role.customer_id != self.customer_id:
            raise ValidationError({"role": "The role must belong to the same customer."})
        if self.is_owner and self.role_id:
            raise ValidationError({"role": "Owners do not require a role."})

    def __str__(self):
        return f"{self.user.email} @ {self.customer}"

    def delete(self, *args, **kwargs):
        if self.is_owner and self.is_active:
            from django.db.models.deletion import ProtectedError
            raise ProtectedError("The active customer owner membership cannot be deleted.", [self])
        return super().delete(*args, **kwargs)
