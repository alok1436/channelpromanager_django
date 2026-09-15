from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from apps.core.viewsets import AuditSoftDeleteMixin
from .models import Company
from .permissions import HasCustomerProfile
from apps.customers.services import get_current_customer
from .serializers import CompanySerializer


class CompanyViewSet(AuditSoftDeleteMixin, ModelViewSet):
    queryset = Company.objects.select_related("customer").all()
    serializer_class = CompanySerializer
    permission_classes = (IsAuthenticated, HasCustomerProfile)
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_module = "companies"
    filterset_fields = ("is_active", "country", "city")
    search_fields = ("name", "email", "phone", "city")
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
