from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.models import TimeStampedModel


class ChannelStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    INACTIVE = "inactive", "Inactive"
    AUTHORIZATION_REQUIRED = "authorization_required", "Authorization Required"
    EXPIRED = "expired", "Expired"
    ERROR = "error", "Error"
    DISCONNECTED = "disconnected", "Disconnected"


class Marketplace(TimeStampedModel):
    platform = models.ForeignKey("platforms.Platform", on_delete=models.PROTECT, related_name="marketplaces")
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=50, unique=True, db_index=True)
    country_code = models.CharField(max_length=2)
    currency_code = models.CharField(max_length=3, blank=True)
    external_marketplace_id = models.CharField(max_length=150, blank=True)
    region = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("platform__name", "country_code", "name")

    def __str__(self):
        return self.name


class Channel(TimeStampedModel):
    customer = models.ForeignKey("customers.Customer", on_delete=models.PROTECT, related_name="channels")
    company = models.ForeignKey("companies.Company", on_delete=models.PROTECT, related_name="channels")
    platform = models.ForeignKey("platforms.Platform", on_delete=models.PROTECT, related_name="channels")
    name = models.CharField(max_length=150)
    country_code = models.CharField(max_length=2)
    vat = models.CharField(max_length=100, blank=True)
    standard_shipping_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    note = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=ChannelStatus.choices, default=ChannelStatus.PENDING, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    authorized_at = models.DateTimeField(null=True, blank=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="channels_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="channels_updated")
    marketplaces = models.ManyToManyField(Marketplace, through="ChannelMarketplace", related_name="channels")

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.UniqueConstraint(fields=("customer", "name"), name="unique_channel_name_per_customer"),
            models.CheckConstraint(condition=Q(standard_shipping_cost__gte=0), name="channel_shipping_cost_nonnegative"),
        ]
        indexes = [
            models.Index(fields=("customer", "platform"), name="channel_customer_platform_idx"),
            models.Index(fields=("customer", "is_active"), name="channel_customer_active_idx"),
            models.Index(fields=("customer", "company"), name="channel_customer_company_idx"),
        ]

    def clean(self):
        if self.company_id and self.customer_id and self.company.customer_id != self.customer_id:
            raise ValidationError({"company": "Company must belong to the channel customer."})

    def __str__(self):
        return self.name


class ChannelMarketplace(TimeStampedModel):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="channel_marketplaces")
    marketplace = models.ForeignKey(Marketplace, on_delete=models.PROTECT, related_name="channel_marketplaces")
    is_enabled = models.BooleanField(default=True)
    orders_enabled = models.BooleanField(default=True)
    listings_enabled = models.BooleanField(default=True)
    inventory_enabled = models.BooleanField(default=True)
    prices_enabled = models.BooleanField(default=True)
    last_orders_sync_at = models.DateTimeField(null=True, blank=True)
    last_listing_sync_at = models.DateTimeField(null=True, blank=True)
    last_inventory_sync_at = models.DateTimeField(null=True, blank=True)
    last_price_sync_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("marketplace__country_code",)
        constraints = [models.UniqueConstraint(fields=("channel", "marketplace"), name="unique_marketplace_per_channel")]

    def clean(self):
        if self.channel_id and self.marketplace_id and self.channel.platform_id != self.marketplace.platform_id:
            raise ValidationError({"marketplace": "Marketplace must belong to the channel platform."})


class AmazonChannelCredential(TimeStampedModel):
    channel = models.OneToOneField(Channel, on_delete=models.CASCADE, related_name="amazon_credentials")
    seller_id = models.CharField(max_length=255)
    refresh_token = models.TextField()
    access_token = models.TextField(blank=True)
    access_token_expires_at = models.DateTimeField(null=True, blank=True)
    last_token_refresh_at = models.DateTimeField(null=True, blank=True)


class EbayChannelCredential(TimeStampedModel):
    channel = models.OneToOneField(Channel, on_delete=models.CASCADE, related_name="ebay_credentials")
    ebay_user_id = models.CharField(max_length=255, blank=True)
    refresh_token = models.TextField()
    access_token = models.TextField(blank=True)
    access_token_expires_at = models.DateTimeField(null=True, blank=True)
    last_token_refresh_at = models.DateTimeField(null=True, blank=True)


class CdiscountChannelCredential(TimeStampedModel):
    channel = models.OneToOneField(Channel, on_delete=models.CASCADE, related_name="cdiscount_credentials")
    seller_id = models.CharField(max_length=255)
    client_id = models.TextField()
    client_secret = models.TextField()


class WooCommerceChannelCredential(TimeStampedModel):
    channel = models.OneToOneField(Channel, on_delete=models.CASCADE, related_name="woocommerce_credentials")
    store_url = models.URLField(max_length=500)
    consumer_key = models.TextField()
    consumer_secret = models.TextField()
    verify_ssl = models.BooleanField(default=True)


class OttoChannelCredential(TimeStampedModel):
    channel = models.OneToOneField(Channel, on_delete=models.CASCADE, related_name="otto_credentials")
    client_id = models.TextField()
    client_secret = models.TextField()


class KauflandChannelCredential(TimeStampedModel):
    channel = models.OneToOneField(Channel, on_delete=models.CASCADE, related_name="kaufland_credentials")
    client_key = models.TextField()
    client_secret = models.TextField()


class ChannelAuthorizationState(TimeStampedModel):
    customer = models.ForeignKey("customers.Customer", on_delete=models.CASCADE, related_name="channel_authorization_states")
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="authorization_states")
    platform = models.ForeignKey("platforms.Platform", on_delete=models.CASCADE, related_name="channel_authorization_states")
    state_hash = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=("platform", "expires_at", "used_at"), name="channel_oauth_state_idx")]


class CustomerAmazonSetting(TimeStampedModel):
    customer = models.OneToOneField("customers.Customer", on_delete=models.CASCADE, related_name="amazon_channel_setting")
    lwa_client_id = models.TextField()
    lwa_client_secret = models.TextField()
    spapi_application_id = models.TextField()
    authorization_url = models.URLField(max_length=500, default="https://sellercentral-europe.amazon.com/apps/authorize/consent")
    oauth_callback_url = models.URLField(max_length=500)
    is_active = models.BooleanField(default=True)


class CustomerEbaySetting(TimeStampedModel):
    customer = models.OneToOneField("customers.Customer", on_delete=models.CASCADE, related_name="ebay_channel_setting")
    client_id = models.TextField()
    client_secret = models.TextField()
    redirect_uri = models.TextField()
    authorization_url = models.URLField(max_length=500, default="https://auth.ebay.com/oauth2/authorize")
    oauth_callback_url = models.URLField(max_length=500)
    oauth_scopes = models.TextField(default="https://api.ebay.com/oauth/api_scope")
    is_active = models.BooleanField(default=True)
