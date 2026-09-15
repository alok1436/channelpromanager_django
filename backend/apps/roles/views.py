from rest_framework.viewsets import ModelViewSet
from apps.core.audit import record_audit
from apps.core.tenant_permissions import CustomerModulePermission
from apps.customers.services import get_current_customer
from apps.core.viewsets import AuditSoftDeleteMixin
from .models import Role
from .serializers import RoleSerializer
class RoleViewSet(AuditSoftDeleteMixin, ModelViewSet):
    queryset = Role.objects.prefetch_related("permissions").all()
    serializer_class = RoleSerializer
    permission_classes = [CustomerModulePermission]
    permission_module = "roles"
    filterset_fields = ("is_active", "is_system_role")
    search_fields = ("name", "slug")
    ordering_fields = ("name", "created_at")

    def get_queryset(self):
        queryset = self.queryset
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(customer=get_current_customer(self.request.user))

    def perform_create(self, serializer):
        if self.request.user.is_superuser:
            instance = serializer.save()
        else:
            instance = serializer.save(customer=get_current_customer(self.request.user), is_system_role=False)
        record_audit(self.request, "created", instance, new_values=serializer.data)
