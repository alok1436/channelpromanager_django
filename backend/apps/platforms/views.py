from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated

from apps.core.permissions import IsSuperAdmin
from apps.core.viewsets import AuditSoftDeleteMixin
from .models import Platform
from .serializers import PlatformSerializer


class PlatformViewSet(AuditSoftDeleteMixin, ModelViewSet):
    queryset = Platform.objects.all()
    serializer_class = PlatformSerializer
    permission_classes = (IsSuperAdmin,)
    filterset_fields = ("is_active",)
    search_fields = ("name", "code", "description")
    ordering_fields = ("name", "code", "created_at", "updated_at")

    def get_permissions(self):
        if getattr(self, "action", None) in {"list", "retrieve"}:
            return [IsAuthenticated()]
        return [IsSuperAdmin()]
