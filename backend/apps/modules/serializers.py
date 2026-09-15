from rest_framework import serializers
from .models import Module
class MatrixPermissionSerializer(serializers.Serializer):
    id = serializers.IntegerField(); name = serializers.CharField(); codename = serializers.CharField()
class ModuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Module
        fields = ("id", "name", "slug", "description", "is_active", "sort_order", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {"is_active": {"default": True}}
class ModuleMatrixSerializer(ModuleSerializer):
    permissions = MatrixPermissionSerializer(many=True, read_only=True)
    class Meta(ModuleSerializer.Meta): fields = ("id", "name", "slug", "permissions")
