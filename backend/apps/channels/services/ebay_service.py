import base64
from datetime import timedelta
from urllib.parse import urlencode

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.channels.models import ChannelStatus, EbayChannelCredential
from .credential_service import set_channel_credentials
from .encryption import decrypt_secret, encrypt_secret
from .http import post_form
from .oauth_state import create_authorization_state, get_locked_authorization_state, mark_authorization_state_used
from .customer_settings import decrypted_provider_setting


EBAY_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"


def _basic_header(credentials):
    value = base64.b64encode(f"{credentials['client_id']}:{credentials['client_secret']}".encode()).decode()
    return {"Authorization": f"Basic {value}"}


def build_ebay_authorization_url(channel):
    if channel.platform.code != "ebay":
        raise serializers.ValidationError({"platform": "Only eBay channels use eBay authorization."})
    setting, credentials = decrypted_provider_setting(channel.customer, "ebay")
    state = create_authorization_state(channel)
    query = urlencode({
        "client_id": credentials["client_id"],
        "redirect_uri": credentials["redirect_uri"],
        "response_type": "code",
        "scope": setting.oauth_scopes,
        "state": state,
    })
    return f"{setting.authorization_url}?{query}"


@transaction.atomic
def complete_ebay_authorization(*, raw_state, authorization_code):
    state = get_locked_authorization_state(raw_state, "ebay")
    setting, credentials = decrypted_provider_setting(state.customer, "ebay")
    payload = post_form(EBAY_TOKEN_URL, {
        "grant_type": "authorization_code", "code": authorization_code,
        "redirect_uri": credentials["redirect_uri"],
    }, headers=_basic_header(credentials))
    if not payload.get("refresh_token"):
        raise serializers.ValidationError({"authorization": "eBay did not return a refresh token."})
    expires_at = timezone.now() + timedelta(seconds=max(int(payload.get("expires_in", 7200)) - 60, 0))
    set_channel_credentials(state.channel, {
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
def get_ebay_access_token(channel):
    if channel.platform.code != "ebay":
        raise serializers.ValidationError({"platform": "Channel is not an eBay channel."})
    credential = EbayChannelCredential.objects.select_for_update().filter(channel=channel).first()
    if credential is None:
        raise serializers.ValidationError({"credentials": "eBay authorization is not configured."})
    if credential.access_token and credential.access_token_expires_at and credential.access_token_expires_at > timezone.now():
        return decrypt_secret(credential.access_token)
    setting, settings_credentials = decrypted_provider_setting(channel.customer, "ebay")
    payload = post_form(EBAY_TOKEN_URL, {
        "grant_type": "refresh_token",
        "refresh_token": decrypt_secret(credential.refresh_token),
        "scope": setting.oauth_scopes,
    }, headers=_basic_header(settings_credentials))
    if not payload.get("access_token"):
        raise serializers.ValidationError({"authorization": "eBay did not return an access token."})
    credential.access_token = encrypt_secret(payload["access_token"])
    credential.access_token_expires_at = timezone.now() + timedelta(seconds=max(int(payload.get("expires_in", 7200)) - 60, 0))
    credential.last_token_refresh_at = timezone.now()
    credential.save(update_fields=("access_token", "access_token_expires_at", "last_token_refresh_at", "updated_at"))
    return payload["access_token"]
