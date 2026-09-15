from rest_framework.viewsets import ModelViewSet
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.core.permissions import IsSuperAdmin
from apps.core.viewsets import AuditSoftDeleteMixin
from .models import Permission
from .serializers import PermissionSerializer
class PermissionViewSet(AuditSoftDeleteMixin, ModelViewSet):
    queryset = Permission.objects.select_related("module").all()
    serializer_class = PermissionSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ("module", "is_active")
    search_fields = ("name", "codename")
    ordering_fields = ("codename", "created_at")

    def get_permissions(self):
        if getattr(self, "action", None) == "list":
            return [IsAuthenticated()]
        return [IsSuperAdmin()]

    def list(self, request, *args, **kwargs):
        modules = {}
        for permission in self.get_queryset().filter(is_active=True, module__is_active=True):
            item = modules.setdefault(permission.module.slug, {"module": permission.module.slug, "name": permission.module.name, "permissions": []})
            item["permissions"].append({"id": permission.id, "code": permission.codename, "name": permission.name})
        return Response(list(modules.values()))
