from django.shortcuts import get_object_or_404

from .models import Channel


def get_customer_channels(customer):
    return Channel.objects.filter(customer=customer).select_related(
        "company", "platform", "created_by", "updated_by",
        "amazon_credentials", "ebay_credentials", "cdiscount_credentials",
        "woocommerce_credentials", "otto_credentials",
    ).prefetch_related("channel_marketplaces__marketplace")


def get_customer_channel(*, customer, channel_id, for_update=False):
    queryset = get_customer_channels(customer)
    if for_update:
        queryset = queryset.select_for_update()
    return get_object_or_404(queryset, pk=channel_id)
