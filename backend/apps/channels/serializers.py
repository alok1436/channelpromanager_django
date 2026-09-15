from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.channels.models import Channel, ChannelMarketplace, Marketplace
from apps.channels.services.channel_service import create_channel, update_channel
from apps.channels.services.credential_service import credential_status, validate_credential_payload
from apps.channels.services.customer_settings import save_provider_setting
from apps.channels.services.encryption import decrypt_secret
from apps.companies.models import Company
from apps.customers.services import get_current_customer
from apps.platforms.models import Platform


class CompanySummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class PlatformSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    code = serializers.CharField()


class MarketplaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marketplace
        fields = (
            "id", "name", "code", "country_code", "currency_code",
            "external_marketplace_id", "region", "is_active",
        )


class MarketplaceAdminSerializer(serializers.ModelSerializer):
    platform_name = serializers.CharField(source="platform.name", read_only=True)
    platform_code = serializers.CharField(source="platform.code", read_only=True)

    class Meta:
        model = Marketplace
        fields = (
            "id", "platform", "platform_name", "platform_code", "name", "code",
            "country_code", "currency_code", "external_marketplace_id", "region",
            "is_active", "created_at", "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")

    def validate(self, attrs):
        platform = attrs.get("platform", getattr(self.instance, "platform", None))
        code = attrs.get("code", getattr(self.instance, "code", "")).strip().lower()
        duplicate = Marketplace.objects.filter(platform=platform, code__iexact=code)
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError({"code": "This marketplace code already exists for the platform."})
        attrs["code"] = code
        if "country_code" in attrs:
            attrs["country_code"] = attrs["country_code"].upper()
        if "currency_code" in attrs:
            attrs["currency_code"] = attrs["currency_code"].upper()
        return attrs


class ChannelMarketplaceSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="marketplace.id", read_only=True)
    name = serializers.CharField(source="marketplace.name", read_only=True)
    code = serializers.CharField(source="marketplace.code", read_only=True)
    country_code = serializers.CharField(source="marketplace.country_code", read_only=True)

    class Meta:
        model = ChannelMarketplace
        fields = (
            "id", "name", "code", "country_code", "is_enabled", "orders_enabled",
            "listings_enabled", "inventory_enabled", "prices_enabled",
            "last_orders_sync_at", "last_listing_sync_at", "last_inventory_sync_at",
            "last_price_sync_at",
        )


class ChannelReadSerializer(serializers.ModelSerializer):
    company = CompanySummarySerializer(read_only=True)
    platform = PlatformSummarySerializer(read_only=True)
    marketplaces = serializers.SerializerMethodField()
    credential_configured = serializers.SerializerMethodField()

    class Meta:
        model = Channel
        fields = (
            "id", "name", "company", "platform", "country_code", "vat",
            "standard_shipping_cost", "note", "status", "is_active", "marketplaces",
            "credential_configured", "authorized_at", "last_sync_at", "created_at", "updated_at",
        )

    @extend_schema_field(ChannelMarketplaceSerializer(many=True))
    def get_marketplaces(self, channel):
        return ChannelMarketplaceSerializer(channel.channel_marketplaces.all(), many=True).data

    @extend_schema_field(serializers.BooleanField())
    def get_credential_configured(self, channel):
        return credential_status(channel)["configured"]


class ChannelCreateSerializer(serializers.Serializer):
    company_id = serializers.PrimaryKeyRelatedField(source="company", queryset=Company.objects.all())
    platform = serializers.SlugRelatedField(slug_field="code", queryset=Platform.objects.filter(is_active=True))
    name = serializers.CharField(max_length=150)
    country_code = serializers.CharField(min_length=2, max_length=2)
    vat = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    standard_shipping_cost = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False, default=Decimal("0"))
    note = serializers.CharField(required=False, allow_blank=True, default="")
    marketplace_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, default=list)
    credentials = serializers.DictField(required=False, write_only=True)

    def validate_country_code(self, value):
        return value.upper()

    def validate(self, attrs):
        customer = get_current_customer(self.context["request"].user)
        company = attrs["company"]
        if company.customer_id != customer.id or not company.is_active or company.deleted_at is not None:
            raise serializers.ValidationError({"company_id": "Select an active company belonging to your customer."})
        if Channel.objects.filter(customer=customer, name__iexact=attrs["name"].strip()).exists():
            raise serializers.ValidationError({"name": "You already have a channel with this name."})
        attrs["name"] = attrs["name"].strip()
        credentials = attrs.get("credentials")
        if credentials and attrs["platform"].code not in {"amazon", "ebay"}:
            attrs["credentials"] = validate_credential_payload(attrs["platform"].code, credentials)
        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        return create_channel(customer=get_current_customer(request.user), user=request.user, **validated_data)


class ChannelUpdateSerializer(serializers.Serializer):
    company_id = serializers.PrimaryKeyRelatedField(source="company", queryset=Company.objects.all(), required=False)
    name = serializers.CharField(max_length=150, required=False)
    country_code = serializers.CharField(min_length=2, max_length=2, required=False)
    vat = serializers.CharField(max_length=100, required=False, allow_blank=True)
    standard_shipping_cost = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0"), required=False)
    note = serializers.CharField(required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)

    def validate_country_code(self, value):
        return value.upper()

    def validate(self, attrs):
        channel = self.instance
        if "company" in attrs and attrs["company"].customer_id != channel.customer_id:
            raise serializers.ValidationError({"company_id": "Select a company belonging to your customer."})
        if "name" in attrs:
            attrs["name"] = attrs["name"].strip()
            if Channel.objects.filter(customer=channel.customer, name__iexact=attrs["name"]).exclude(pk=channel.pk).exists():
                raise serializers.ValidationError({"name": "You already have a channel with this name."})
        return attrs

    def update(self, instance, validated_data):
        return update_channel(instance, user=self.context["request"].user, **validated_data)


class ChannelCredentialUpdateSerializer(serializers.Serializer):
    seller_id = serializers.CharField(required=False)
    ebay_user_id = serializers.CharField(required=False, allow_blank=True)
    refresh_token = serializers.CharField(required=False, write_only=True)
    access_token = serializers.CharField(required=False, write_only=True, allow_blank=True)
    access_token_expires_at = serializers.DateTimeField(required=False, write_only=True, allow_null=True)
    client_id = serializers.CharField(required=False, write_only=True)
    client_secret = serializers.CharField(required=False, write_only=True)
    store_url = serializers.URLField(required=False)
    consumer_key = serializers.CharField(required=False, write_only=True)
    consumer_secret = serializers.CharField(required=False, write_only=True)
    verify_ssl = serializers.BooleanField(required=False)

    def validate(self, attrs):
        return validate_credential_payload(self.context["channel"].platform.code, attrs, partial=True)


class MarketplaceReplaceSerializer(serializers.Serializer):
    marketplace_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), allow_empty=True)


class AuthorizationCallbackSerializer(serializers.Serializer):
    state = serializers.CharField()
    code = serializers.CharField(required=False)
    spapi_oauth_code = serializers.CharField(required=False)
    selling_partner_id = serializers.CharField(required=False)


class AmazonCustomerSettingSerializer(serializers.Serializer):
    lwa_client_id = serializers.CharField(required=False, allow_blank=True)
    lwa_client_secret = serializers.CharField(required=False, allow_blank=True, write_only=True)
    spapi_application_id = serializers.CharField(required=False, allow_blank=True)
    authorization_url = serializers.URLField(required=False)
    oauth_callback_url = serializers.URLField(required=False)
    is_active = serializers.BooleanField(required=False)


class EbayCustomerSettingSerializer(serializers.Serializer):
    client_id = serializers.CharField(required=False, allow_blank=True)
    client_secret = serializers.CharField(required=False, allow_blank=True, write_only=True)
    redirect_uri = serializers.CharField(required=False, allow_blank=True)
    authorization_url = serializers.URLField(required=False)
    oauth_callback_url = serializers.URLField(required=False)
    oauth_scopes = serializers.CharField(required=False, allow_blank=False)
    is_active = serializers.BooleanField(required=False)


class CustomerChannelSettingsSerializer(serializers.Serializer):
    amazon = AmazonCustomerSettingSerializer(required=False)
    ebay = EbayCustomerSettingSerializer(required=False)

    def update_customer(self, customer):
        for provider, values in self.validated_data.items():
            save_provider_setting(customer, provider, values)


def customer_channel_settings_data(customer):
    data = {}
    for provider, related_name, public_encrypted in (
        ("amazon", "amazon_channel_setting", ("lwa_client_id", "spapi_application_id")),
        ("ebay", "ebay_channel_setting", ("client_id", "redirect_uri")),
    ):
        try:
            setting = getattr(customer, related_name)
        except ObjectDoesNotExist:
            data[provider] = {"configured": False, "secret_configured": False}
            continue
        fields = {field: decrypt_secret(getattr(setting, field)) for field in public_encrypted}
        for field in ("authorization_url", "oauth_callback_url", "is_active"):
            fields[field] = getattr(setting, field)
        if provider == "ebay":
            fields["oauth_scopes"] = setting.oauth_scopes
        fields.update({"configured": True, "secret_configured": True})
        data[provider] = fields
    return data
