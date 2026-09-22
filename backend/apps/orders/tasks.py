from celery import shared_task
import os
import uuid

from redis import Redis

from apps.channels.models import Channel, ChannelStatus
from .services import get_order_service


@shared_task(autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries": 3})
def sync_channel_orders(channel_id):
    lock_key = f"order-sync-lock:{channel_id}"
    redis = Redis.from_url(os.environ.get("REDIS_URL", "redis://redis:6379/0"))
    lock_value = uuid.uuid4().hex
    if not redis.set(lock_key, lock_value, nx=True, ex=600):
        return {"skipped": "A sync is already running for this channel."}
    try:
        channel = Channel.objects.select_related("platform", "customer").get(pk=channel_id, is_active=True)
        return get_order_service(channel).download_orders().as_dict()
    finally:
        redis.eval("if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end", 1, lock_key, lock_value)


@shared_task
def schedule_kaufland_orders():
    """Queue one sync per active, configured Kaufland channel every five minutes."""
    channel_ids = Channel.objects.filter(
        platform__code="kaufland", is_active=True, status=ChannelStatus.ACTIVE,
        kaufland_credentials__isnull=False,
        channel_marketplaces__is_enabled=True, channel_marketplaces__orders_enabled=True,
        channel_marketplaces__marketplace__is_active=True,
    ).values_list("id", flat=True).distinct()
    for channel_id in channel_ids:
        sync_channel_orders.delay(channel_id)
