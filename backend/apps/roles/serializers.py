from django.db import transaction
from django.utils.text import slugify
from rest_framework import serializers
from apps.permissions.models import Permission
from .models import Role, RolePermission
class PermissionCodenameListField(serializers.ListField):
    child = serializers.CharField()
    def to_internal_value(self, data):
        codenames = super().to_internal_value(data)
        found = {p.codename: p for p in Permission.objects.filter(is_active=True, codename__in=codenames)}
        missing = [code for code in codenames if code not in found]
        if missing: raise serializers.ValidationError(f"Unknown or inactive permissions: {', '.join(missing)}")
        return [found[code] for code in dict.fromkeys(codenames)]
    def to_representation(self, value):
        iterable = value.all() if hasattr(value, "all") else value
        return [permission.codename for permission in iterable]
class RoleSerializer(serializers.ModelSerializer):
    permissions = PermissionCodenameListField(required=False)
    class Meta:
        model = Role
        fields = ("id", "customer", "name", "slug", "description", "is_system_role", "is_active", "permissions", "created_at", "updated_at")
        read_only_fields = ("is_system_role", "created_at", "updated_at")
        extra_kwargs = {"slug": {"required": False}, "is_active": {"default": True}}
        validators = []
    def validate_slug(self, value): return value or slugify(self.initial_data.get("name", ""))
    def validate(self, attrs):
        if self.instance and self.instance.is_system_role:
            if attrs.get("is_active") is False:
                raise serializers.ValidationError({"is_active": "System roles cannot be deactivated."})
            if "customer" in attrs and attrs["customer"] != self.instance.customer:
                raise serializers.ValidationError({"customer": "Role ownership cannot be changed."})
        if self.instance and "customer" in attrs and attrs["customer"] != self.instance.customer:
            raise serializers.ValidationError({"customer": "Role ownership cannot be changed."})
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        slug = attrs.get("slug") or getattr(self.instance, "slug", None) or slugify(attrs.get("name", ""))
        duplicate = Role.objects.filter(customer=customer, slug=slug)
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError({"slug": "A role with this slug already exists for the customer."})
        return attrs
    @transaction.atomic
    def create(self, validated_data):
        permissions = validated_data.pop("permissions", []); validated_data.setdefault("slug", slugify(validated_data["name"])); role = Role.objects.create(**validated_data)
        RolePermission.objects.bulk_create([RolePermission(role=role, permission=p) for p in permissions]); return role
    @transaction.atomic
    def update(self, instance, validated_data):
        permissions = validated_data.pop("permissions", None); instance = super().update(instance, validated_data)
        if permissions is not None:
            instance.role_permissions.exclude(permission__in=permissions).delete()
            existing = set(instance.role_permissions.values_list("permission_id", flat=True))
            RolePermission.objects.bulk_create([RolePermission(role=instance, permission=p) for p in permissions if p.id not in existing])
        return instance
