import hashlib
import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.channels.models import ChannelAuthorizationState


def state_digest(raw_state):
    return hashlib.sha256(raw_state.encode()).hexdigest()


def create_authorization_state(channel, lifetime_minutes=10):
    raw_state = secrets.token_urlsafe(48)
    ChannelAuthorizationState.objects.create(
        customer=channel.customer,
        channel=channel,
        platform=channel.platform,
        state_hash=state_digest(raw_state),
        expires_at=timezone.now() + timedelta(minutes=lifetime_minutes),
    )
    return raw_state


def get_locked_authorization_state(raw_state, platform_code):
    try:
        state = ChannelAuthorizationState.objects.select_for_update().select_related(
            "channel", "channel__platform", "customer", "platform"
        ).get(state_hash=state_digest(raw_state), platform__code=platform_code)
    except ChannelAuthorizationState.DoesNotExist as exc:
        raise serializers.ValidationError({"state": "Invalid authorization state."}) from exc
    if state.used_at is not None:
        raise serializers.ValidationError({"state": "Authorization state has already been used."})
    if state.expires_at <= timezone.now():
        raise serializers.ValidationError({"state": "Authorization state has expired."})
    if state.channel.customer_id != state.customer_id or state.channel.platform_id != state.platform_id:
        raise serializers.ValidationError({"state": "Authorization state does not match its channel."})
    return state


def mark_authorization_state_used(state):
    state.used_at = timezone.now()
    state.save(update_fields=("used_at", "updated_at"))

