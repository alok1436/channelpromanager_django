from django.db import transaction
from rest_framework.viewsets import ModelViewSet
from apps.core.permissions import HasModulePermission
from apps.core.viewsets import AuditSoftDeleteMixin
from .models import Customer
from .serializers import CustomerSerializer
from .filters import CustomerFilter
class CustomerViewSet(AuditSoftDeleteMixin, ModelViewSet):
    queryset = Customer.objects.select_related("user").prefetch_related("memberships__role").filter(
        deleted_at__isnull=True,
    ).order_by("-created_at")
    serializer_class = CustomerSerializer
    permission_classes = [HasModulePermission]
    permission_module = "customers"
    filterset_class = CustomerFilter
    search_fields = ("first_name", "last_name", "email", "company")
    ordering_fields = ("created_at", "first_name", "last_name", "company")

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        customer = self.get_object()
        response = super().destroy(request, *args, **kwargs)
        if customer.user_id and not customer.user.is_superuser:
            customer.user.is_active = False
            customer.user.save(update_fields=("is_active", "updated_at"))
        return response
