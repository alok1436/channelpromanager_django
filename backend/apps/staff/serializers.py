from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from apps.customers.models import Customer, CustomerMembership
from apps.customers.services import get_current_customer
from apps.roles.models import Role
from apps.users.models import User


class StaffSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    email = serializers.EmailField(source="user.email")
    first_name = serializers.CharField(source="user.first_name")
    last_name = serializers.CharField(source="user.last_name")
    phone = serializers.CharField(source="user.phone", required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False)
    role_id = serializers.PrimaryKeyRelatedField(source="role", queryset=Role.objects.filter(is_active=True), required=True)
    role_name = serializers.CharField(source="role.name", read_only=True)
    customer_id = serializers.PrimaryKeyRelatedField(source="customer", queryset=Customer.objects.filter(is_active=True), write_only=True, required=False)

    class Meta:
        model = CustomerMembership
        fields = ("id", "user_id", "customer_id", "email", "first_name", "last_name", "phone", "password", "role_id", "role_name", "is_active", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")

    def validate(self, attrs):
        request = self.context["request"]
        supplied_customer = attrs.get("customer")
        customer = supplied_customer if request.user.is_superuser else get_current_customer(request.user)
        if not request.user.is_superuser and supplied_customer and supplied_customer != customer:
            raise serializers.ValidationError({"customer_id": "Customer context cannot be overridden."})
        attrs["customer"] = customer
        role = attrs.get("role", getattr(self.instance, "role", None))
        if not customer:
            raise serializers.ValidationError({"customer": "A customer context is required."})
        if role and role.customer_id != customer.id:
            raise serializers.ValidationError({"role_id": "The role must belong to your customer."})
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "A password is required when creating staff."})
        password = attrs.get("password")
        user_data = attrs.get("user", {})
        email = user_data.get("email", getattr(getattr(self.instance, "user", None), "email", None))
        duplicate = User.objects.filter(email__iexact=email)
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.user_id)
        if duplicate.exists():
            raise serializers.ValidationError({"email": "A user with this email already exists."})
        if password:
            try:
                validate_password(password, User(email=email, first_name=user_data.get("first_name", ""), last_name=user_data.get("last_name", "")))
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop("user")
        password = validated_data.pop("password")
        customer = validated_data.pop("customer", self.context.get("customer"))
        user = User.objects.create_user(password=password, **user_data)
        return CustomerMembership.objects.create(customer=customer, user=user, is_owner=False, **validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        user_data = validated_data.pop("user", {})
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        user = instance.user
        for field, value in user_data.items():
            setattr(user, field, value)
        if password:
            user.set_password(password)
        user.is_active = instance.is_active
        user.save()
        return instance
