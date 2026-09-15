from rest_framework import serializers
from .models import Permission
class PermissionSerializer(serializers.ModelSerializer):
    module_name = serializers.CharField(source="module.name", read_only=True)
    class Meta:
        model = Permission
        fields = ("id", "module", "module_name", "name", "codename", "description", "is_active", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {"is_active": {"default": True}}
    def validate(self, attrs):
        module = attrs.get("module", getattr(self.instance, "module", None)); codename = attrs.get("codename", getattr(self.instance, "codename", ""))
        if module and not codename.startswith(f"{module.slug}."): raise serializers.ValidationError({"codename": "Codename must start with the module slug."})
        return attrs
