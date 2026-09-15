from datetime import timedelta
from urllib.parse import urlencode

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.channels.models import AmazonChannelCredential, ChannelStatus
from .credential_service import set_channel_credentials
from .encryption import decrypt_secret, encrypt_secret
from .http import post_form
from .oauth_state import create_authorization_state, get_locked_authorization_state, mark_authorization_state_used
from .customer_settings import decrypted_provider_setting


LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"


def build_amazon_authorization_url(channel):
    if channel.platform.code != "amazon":
        raise serializers.ValidationError({"platform": "Only Amazon channels use Amazon authorization."})
    setting, credentials = decrypted_provider_setting(channel.customer, "amazon")
    state = create_authorization_state(channel)
    query = urlencode({"application_id": credentials["spapi_application_id"], "state": state})
    return f"{setting.authorization_url}?{query}"


@transaction.atomic
def complete_amazon_authorization(*, raw_state, authorization_code, seller_id):
    state = get_locked_authorization_state(raw_state, "amazon")
    _, credentials = decrypted_provider_setting(state.customer, "amazon")
    payload = post_form(LWA_TOKEN_URL, {
        "grant_type": "authorization_code",
        "code": authorization_code,
        "client_id": credentials["lwa_client_id"],
        "client_secret": credentials["lwa_client_secret"],
    })
    if not payload.get("refresh_token"):
        raise serializers.ValidationError({"authorization": "Amazon did not return a refresh token."})
    expires_at = timezone.now() + timedelta(seconds=max(int(payload.get("expires_in", 3600)) - 60, 0))
    set_channel_credentials(state.channel, {
        "seller_id": seller_id,
        "refresh_token": payload["refresh_token"],
        "access_token": payload.get("access_token", ""),
        "access_token_expires_at": expires_at,
    })
    state.channel.status = ChannelStatus.ACTIVE
    state.channel.authorized_at = timezone.now()
    state.channel.is_active = True
    state.channel.save(update_fields=("status", "authorized_at", "is_active", "updated_at"))
    mark_authorization_state_used(state)
    return state.channel


@transaction.atomic
def get_amazon_access_token(channel):
    if channel.platform.code != "amazon":
        raise serializers.ValidationError({"platform": "Channel is not an Amazon channel."})
    credential = AmazonChannelCredential.objects.select_for_update().filter(channel=channel).first()
    if credential is None:
        raise serializers.ValidationError({"credentials": "Amazon authorization is not configured."})
    if credential.access_token and credential.access_token_expires_at and credential.access_token_expires_at > timezone.now():
        return decrypt_secret(credential.access_token)
    _, settings_credentials = decrypted_provider_setting(channel.customer, "amazon")
    payload = post_form(LWA_TOKEN_URL, {
        "grant_type": "refresh_token",
        "refresh_token": decrypt_secret(credential.refresh_token),
        "client_id": settings_credentials["lwa_client_id"],
        "client_secret": settings_credentials["lwa_client_secret"],
    })
    if not payload.get("access_token"):
        raise serializers.ValidationError({"authorization": "Amazon did not return an access token."})
    credential.access_token = encrypt_secret(payload["access_token"])
    credential.access_token_expires_at = timezone.now() + timedelta(seconds=max(int(payload.get("expires_in", 3600)) - 60, 0))
    credential.last_token_refresh_at = timezone.now()
    credential.save(update_fields=("access_token", "access_token_expires_at", "last_token_refresh_at", "updated_at"))
    return payload["access_token"]
