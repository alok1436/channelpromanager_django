from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.users.models import User
from .models import Customer, CustomerMembership


class CustomerSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    has_login = serializers.SerializerMethodField()
    password = serializers.CharField(write_only=True, required=False, trim_whitespace=False, style={"input_type": "password"})

    class Meta:
        model = Customer
        fields = ("id", "user", "has_login", "password", "first_name", "last_name", "company", "phone", "email", "address", "open_date", "is_active", "created_at", "updated_at")
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {"is_active": {"default": True}}

    @extend_schema_field(serializers.BooleanField())
    def get_has_login(self, customer):
        return customer.user_id is not None

    def validate(self, attrs):
        password = attrs.get("password")
        if self.instance is None and not password:
            raise serializers.ValidationError({"password": "A password is required to create the customer login."})
        email = attrs.get("email", getattr(self.instance, "email", None))
        linked_user_id = getattr(self.instance, "user_id", None)
        duplicate_user = User.objects.filter(email__iexact=email)
        if linked_user_id:
            duplicate_user = duplicate_user.exclude(pk=linked_user_id)
        if email and duplicate_user.exists():
            raise serializers.ValidationError({"email": "A login account with this email already exists."})
        if password:
            password_user = self.instance.user if self.instance and self.instance.user_id else User(
                email=email,
                first_name=attrs.get("first_name", getattr(self.instance, "first_name", "")),
                last_name=attrs.get("last_name", getattr(self.instance, "last_name", "")),
            )
            try:
                validate_password(password, user=password_user)
            except DjangoValidationError as exc:
                raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User.objects.create_user(
            email=validated_data["email"], password=password,
            first_name=validated_data["first_name"], last_name=validated_data["last_name"],
            is_active=validated_data.get("is_active", True),
        )
        customer = Customer.objects.create(user=user, **validated_data)
        CustomerMembership.objects.create(customer=customer, user=user, is_owner=True, is_active=True)
        return customer

    @transaction.atomic
    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        instance = super().update(instance, validated_data)
        if instance.user_id:
            user = instance.user
            if not user.is_superuser:
                user.email = instance.email
                user.first_name = instance.first_name
                user.last_name = instance.last_name
                user.is_active = instance.is_active
                update_fields = ["email", "first_name", "last_name", "is_active", "updated_at"]
                if password:
                    user.set_password(password)
                    update_fields.append("password")
                user.save(update_fields=update_fields)
        elif password:
            instance.user = User.objects.create_user(
                email=instance.email, password=password, first_name=instance.first_name,
                last_name=instance.last_name, is_active=instance.is_active,
            )
            instance.save(update_fields=("user", "updated_at"))
            CustomerMembership.objects.get_or_create(customer=instance, user=instance.user, defaults={"is_owner": True, "is_active": True})
        return instance
