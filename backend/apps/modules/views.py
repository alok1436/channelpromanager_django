from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet
from apps.core.permissions import IsSuperAdmin
from apps.core.viewsets import AuditSoftDeleteMixin
from .models import Module
from .serializers import ModuleSerializer, ModuleMatrixSerializer
class ModuleViewSet(AuditSoftDeleteMixin, ModelViewSet):
    queryset = Module.objects.prefetch_related("permissions").all()
    serializer_class = ModuleSerializer
    permission_classes = [IsSuperAdmin]
    filterset_fields = ("is_active",)
    search_fields = ("name", "slug")
    ordering_fields = ("sort_order", "name", "created_at")
    @action(detail=False, methods=["get"], url_path="permission-matrix")
    def permission_matrix(self, request):
        qs = self.get_queryset().filter(is_active=True, permissions__is_active=True).distinct()
        return Response(ModuleMatrixSerializer(qs, many=True).data)
