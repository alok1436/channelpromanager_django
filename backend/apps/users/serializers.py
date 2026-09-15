from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from apps.core.permissions import effective_permission_codenames
from apps.customers.services import effective_customer_permissions, get_customer_membership
class RoleSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField(); name = serializers.CharField()
class MeSerializer(serializers.Serializer):
    id = serializers.IntegerField(); email = serializers.EmailField(); first_name = serializers.CharField(); last_name = serializers.CharField(); is_superuser = serializers.BooleanField()
    roles = serializers.SerializerMethodField(); permissions = serializers.SerializerMethodField()
    customer = serializers.SerializerMethodField()
    membership = serializers.SerializerMethodField()
    @extend_schema_field(RoleSummarySerializer(many=True))
    def get_roles(self, user):
        membership = get_customer_membership(user)
        roles = [membership.role] if membership and membership.role_id and membership.role.is_active else []
        return RoleSummarySerializer(roles, many=True).data
    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_permissions(self, user):
        membership = get_customer_membership(user)
        return effective_customer_permissions(user, membership) if membership else sorted(effective_permission_codenames(user))
    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_customer(self, user):
        membership = get_customer_membership(user)
        if not membership: return None
        return {"id": membership.customer_id, "company_name": membership.customer.company, "email": membership.customer.email}
    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_membership(self, user):
        membership = get_customer_membership(user)
        if not membership: return None
        return {"id": membership.id, "is_owner": membership.is_owner, "has_full_access": membership.is_owner, "role": {"id": membership.role_id, "name": membership.role.name} if membership.role_id else None}
class RefreshTokenSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True)
class CurrentPermissionsSerializer(serializers.Serializer):
    is_superuser = serializers.BooleanField()
    permissions = serializers.DictField(child=serializers.DictField(child=serializers.BooleanField()))
