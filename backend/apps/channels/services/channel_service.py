from django.db import transaction
from rest_framework import serializers

from apps.channels.models import Channel, ChannelMarketplace, ChannelStatus, Marketplace
from .credential_service import set_channel_credentials


OAUTH_PLATFORMS = {"amazon", "ebay"}


def validate_marketplaces(platform, marketplace_ids):
    marketplace_ids = list(dict.fromkeys(marketplace_ids or []))
    marketplaces = list(Marketplace.objects.filter(id__in=marketplace_ids, is_active=True))
    if len(marketplaces) != len(marketplace_ids):
        raise serializers.ValidationError({"marketplace_ids": "One or more marketplaces are invalid or inactive."})
    if any(item.platform_id != platform.id for item in marketplaces):
        raise serializers.ValidationError({"marketplace_ids": "Every marketplace must belong to the channel platform."})
    return marketplaces


@transaction.atomic
def create_channel(*, customer, user, company, platform, marketplace_ids=None, credentials=None, **fields):
    if company.customer_id != customer.id or not company.is_active or company.deleted_at is not None:
        raise serializers.ValidationError({"company_id": "Select an active company belonging to your customer."})
    marketplaces = validate_marketplaces(platform, marketplace_ids)
    if platform.code in OAUTH_PLATFORMS and credentials:
        raise serializers.ValidationError({"credentials": f"{platform.name} credentials must be configured through authorization."})
    status = ChannelStatus.AUTHORIZATION_REQUIRED if platform.code in OAUTH_PLATFORMS else ChannelStatus.PENDING
    channel = Channel.objects.create(
        customer=customer, company=company, platform=platform, created_by=user, updated_by=user,
        status=status, **fields,
    )
    ChannelMarketplace.objects.bulk_create(
        [ChannelMarketplace(channel=channel, marketplace=marketplace) for marketplace in marketplaces]
    )
    if credentials:
        set_channel_credentials(channel, credentials)
        channel.status = ChannelStatus.ACTIVE
        channel.save(update_fields=("status", "updated_at"))
    return channel


@transaction.atomic
def update_channel(channel, *, user, company=None, **fields):
    if company is not None:
        if company.customer_id != channel.customer_id or not company.is_active or company.deleted_at is not None:
            raise serializers.ValidationError({"company_id": "Select an active company belonging to your customer."})
        channel.company = company
    for key, value in fields.items():
        setattr(channel, key, value)
    channel.updated_by = user
    channel.save()
    return channel


@transaction.atomic
def replace_channel_marketplaces(channel, marketplace_ids):
    marketplaces = validate_marketplaces(channel.platform, marketplace_ids)
    requested = {marketplace.id for marketplace in marketplaces}
    channel.channel_marketplaces.exclude(marketplace_id__in=requested).delete()
    existing = set(channel.channel_marketplaces.values_list("marketplace_id", flat=True))
    ChannelMarketplace.objects.bulk_create(
        [ChannelMarketplace(channel=channel, marketplace=item) for item in marketplaces if item.id not in existing]
    )
    return channel.channel_marketplaces.select_related("marketplace")


@transaction.atomic
def disconnect_channel(channel, user):
    channel.status = ChannelStatus.DISCONNECTED
    channel.is_active = False
    channel.updated_by = user
    channel.save(update_fields=("status", "is_active", "updated_by", "updated_at"))
    return channel

