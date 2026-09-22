from rest_framework.viewsets import ModelViewSet
from apps.core.audit import record_audit
from apps.core.tenant_permissions import CustomerModulePermission
from apps.customers.services import get_current_customer
from apps.core.viewsets import AuditSoftDeleteMixin
from .models import Order
from .serializers import OrderSerializer
class OrderViewSet(AuditSoftDeleteMixin, ModelViewSet):
    queryset = Order.objects.select_related("customer", "channel", "marketplace").prefetch_related("items").all()
    serializer_class = OrderSerializer
    permission_classes = [CustomerModulePermission]
    permission_module = "orders"
    filterset_fields = ("status", "external_status", "customer", "channel", "marketplace", "currency", "fulfillment_channel")
    search_fields = ("order_number", "external_order_id", "seller_order_id", "buyer_email", "buyer_name", "items__sku", "items__asin")
    ordering_fields = ("created_at", "purchase_date", "last_update_date", "order_number", "total")

    def get_queryset(self):
        queryset = self.queryset
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(customer=get_current_customer(self.request.user))

    def perform_create(self, serializer):
        if self.request.user.is_superuser:
            instance = serializer.save()
        else:
            instance = serializer.save(customer=get_current_customer(self.request.user))
        record_audit(self.request, "created", instance, new_values=serializer.data)
