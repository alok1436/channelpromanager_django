from django.db import transaction
from rest_framework.exceptions import PermissionDenied
from rest_framework.viewsets import ModelViewSet

from apps.core.tenant_permissions import CustomerModulePermission
from apps.customers.models import CustomerMembership
from apps.customers.services import get_current_customer
from .serializers import StaffSerializer


class StaffViewSet(ModelViewSet):
    queryset = CustomerMembership.objects.filter(is_owner=False).select_related("user", "role", "customer")
    serializer_class = StaffSerializer
    permission_classes = (CustomerModulePermission,)
    permission_module = "staff"
    search_fields = ("user__email", "user__first_name", "user__last_name")
    ordering_fields = ("created_at", "user__email")

    def get_queryset(self):
        queryset = self.queryset
        if getattr(self, "swagger_fake_view", False):
            return queryset.none()
        if self.request.user.is_superuser:
            return queryset
        return queryset.filter(customer=get_current_customer(self.request.user))

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if not self.request.user.is_superuser:
            context["customer"] = get_current_customer(self.request.user)
        return context

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        if serializer.instance.user_id == self.request.user.id:
            raise PermissionDenied("Staff cannot change their own role or membership.")
        serializer.save()

    @transaction.atomic
    def perform_destroy(self, instance):
        if instance.user_id == self.request.user.id:
            raise PermissionDenied("Staff cannot delete their own membership.")
        instance.is_active = False
        instance.save(update_fields=("is_active", "updated_at"))
        if not instance.user.customer_memberships.filter(is_active=True).exists():
            instance.user.is_active = False
            instance.user.save(update_fields=("is_active", "updated_at"))
