from rest_framework import serializers

from apps.customers.models import Customer
from apps.customers.services import get_current_customer
from .models import Company


class CompanySerializer(serializers.ModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(
        queryset=Customer.objects.filter(is_active=True), required=False
    )

    class Meta:
        model = Company
        fields = (
            "id", "customer", "name", "street_1",
            "street_2", "postal_code", "city", "province", "country",
            "phone", "fax", "email", "logo", "note", "is_active",
            "created_at", "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {"is_active": {"default": True}}
        validators = []

    def validate_logo(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Logo must be 5 MB or smaller.")
        allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
        if value and getattr(value, "content_type", None) not in allowed_types:
            raise serializers.ValidationError("Logo must be a JPEG, PNG, WebP, or GIF image.")
        return value

    def validate(self, attrs):
        request = self.context["request"]
        supplied_customer = attrs.get("customer")
        if request.user.is_superuser:
            if self.instance is None and supplied_customer is None:
                raise serializers.ValidationError({"customer": "This field is required for superadmins."})
        else:
            customer = get_current_customer(request.user)
            if supplied_customer is not None and supplied_customer.pk != customer.pk:
                raise serializers.ValidationError({"customer": "You cannot create a company for another customer."})
            attrs["customer"] = customer
        if self.instance and supplied_customer and supplied_customer.pk != self.instance.customer_id:
            raise serializers.ValidationError({"customer": "Company ownership cannot be changed."})
        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        name = attrs.get("name", getattr(self.instance, "name", None))
        duplicates = Company.objects.filter(customer=customer, name__iexact=name, is_active=True)
        if self.instance:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if customer and name and duplicates.exists():
            raise serializers.ValidationError({"name": "You already have an active company with this name."})
        return attrs
