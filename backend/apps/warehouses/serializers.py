from rest_framework import serializers

from apps.companies.models import Company
from apps.customers.models import Customer
from apps.customers.services import get_current_customer
from .models import Warehouse


class WarehouseSerializer(serializers.ModelSerializer):
    customer = serializers.PrimaryKeyRelatedField(read_only=True)
    customer_id = serializers.PrimaryKeyRelatedField(
        source="customer", queryset=Customer.objects.filter(is_active=True),
        write_only=True, required=False,
    )
    company = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.filter(is_active=True, deleted_at__isnull=True),
        required=True,
    )
    company_name = serializers.CharField(source="company.name", read_only=True)

    class Meta:
        model = Warehouse
        fields = (
            "id", "customer", "customer_id", "company", "company_name", "name", "street1", "street2",
            "plz", "city", "province", "country", "phone", "fax", "email",
            "notes", "created_at", "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")
        validators = []

    def validate(self, attrs):
        request = self.context["request"]
        supplied_customer = attrs.get("customer")
        if request.user.is_superuser:
            if self.instance is None and supplied_customer is None:
                raise serializers.ValidationError({"customer_id": "This field is required for superadmins."})
        else:
            current_customer = get_current_customer(request.user)
            if supplied_customer is not None and supplied_customer.pk != current_customer.pk:
                raise serializers.ValidationError({"customer_id": "You cannot use another customer account."})
            attrs["customer"] = current_customer
        if self.instance and supplied_customer and supplied_customer.pk != self.instance.customer_id:
            raise serializers.ValidationError({"customer_id": "Warehouse ownership cannot be changed."})

        customer = attrs.get("customer", getattr(self.instance, "customer", None))
        company = attrs.get("company", getattr(self.instance, "company", None))
        if company and customer and company.customer_id != customer.id:
            raise serializers.ValidationError({"company": "Select a company belonging to this customer."})
        if self.instance and "company" in attrs and company.customer_id != self.instance.customer_id:
            raise serializers.ValidationError({"company": "Warehouse company must belong to the same customer."})

        name = attrs.get("name", getattr(self.instance, "name", ""))
        duplicate = Warehouse.objects.filter(customer=customer, name__iexact=name)
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if customer and name and duplicate.exists():
            raise serializers.ValidationError({"name": "You already have a warehouse with this name."})
        return attrs
