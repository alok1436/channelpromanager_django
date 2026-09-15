from rest_framework.viewsets import ModelViewSet

from apps.core.audit import record_audit
from apps.core.tenant_permissions import CustomerModulePermission
from apps.customers.services import get_current_customer
from .models import Warehouse
from .serializers import WarehouseSerializer


class WarehouseViewSet(ModelViewSet):
    queryset = Warehouse.objects.select_related("customer", "company").all()
    serializer_class = WarehouseSerializer
    permission_classes = (CustomerModulePermission,)
    permission_module = "warehouses"
    filterset_fields = ("customer", "company", "country", "city")
    search_fields = ("name", "company__name", "email", "phone", "city")
    ordering_fields = ("name", "created_at", "updated_at")

    def get_queryset(self):
        queryset = self.queryset
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        if self.request.user.is_superuser:
            return queryset
        if not self.request.user.is_authenticated:
            return queryset.none()
        return queryset.filter(customer=get_current_customer(self.request.user))

    def perform_create(self, serializer):
        if self.request.user.is_superuser:
            instance = serializer.save()
        else:
            instance = serializer.save(customer=get_current_customer(self.request.user))
        record_audit(self.request, "created", instance, new_values=serializer.data)
