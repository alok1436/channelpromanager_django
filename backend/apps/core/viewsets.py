from django.utils import timezone
from rest_framework.response import Response
from rest_framework import status
from .audit import record_audit

class AuditSoftDeleteMixin:
    def perform_create(self, serializer):
        instance = serializer.save()
        record_audit(self.request, "created", instance, new_values=serializer.data)
    def perform_update(self, serializer):
        old = self.get_serializer(serializer.instance).data
        instance = serializer.save()
        record_audit(self.request, "updated", instance, old_values=old, new_values=serializer.data)
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if getattr(instance, "is_system_role", False):
            return Response({"success": False, "message": "System roles cannot be deleted."}, status=status.HTTP_400_BAD_REQUEST)
        old = self.get_serializer(instance).data
        if hasattr(instance, "is_active"):
            instance.is_active = False
            if hasattr(instance, "deleted_at"): instance.deleted_at = timezone.now()
            instance.save()
            record_audit(request, "deleted", instance, old_values=old)
        else:
            record_audit(request, "deleted", instance, old_values=old)
            instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
