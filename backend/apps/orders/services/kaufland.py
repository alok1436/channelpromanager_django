"""Kaufland Seller API v2 order importer."""

import hashlib
import hmac
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

import httpx
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from apps.channels.models import KauflandChannelCredential
from apps.channels.services.encryption import decrypt_secret
from apps.channels.services.http import ProviderRequestError
from apps.orders.models import Order, OrderItem
from apps.products.models import Product
from .base import BaseOrderService, OrderSyncResult


BASE_URL = "https://sellerapi.kaufland.com/v2"


def sign_request(method, url, body, timestamp, secret):
    message = "\n".join((method.upper(), url, body, str(timestamp)))
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def cents(value):
    return Decimal(str(value or 0)) / 100


def order_status(units):
    statuses = {unit.get("status") for unit in units}
    if statuses and statuses <= {"cancelled", "refunded"}:
        return Order.Status.CANCELLED
    if statuses and statuses <= {"sent", "received", "fulfilled"}:
        return Order.Status.COMPLETED
    if statuses & {"open", "need_to_be_sent", "need_to_be_fulfilled", "in_fulfillment", "sent"}:
        return Order.Status.PROCESSING
    return Order.Status.PENDING


class KauflandOrderService(BaseOrderService):
    """Import selected storefronts using encrypted per-channel Seller API keys."""

    def __init__(self, channel, *, client=None):
        super().__init__(channel)
        if channel.platform.code != "kaufland":
            raise serializers.ValidationError({"platform": "Channel is not a Kaufland channel."})
        credential = KauflandChannelCredential.objects.filter(channel=channel).first()
        if credential is None:
            raise serializers.ValidationError({"credentials": "Kaufland API keys are not configured."})
        self.client_key = decrypt_secret(credential.client_key)
        self.client_secret = decrypt_secret(credential.client_secret)
        self.client = client or httpx.Client(timeout=30)
        self.marketplaces = list(channel.channel_marketplaces.select_related("marketplace").filter(
            is_enabled=True, orders_enabled=True, marketplace__is_active=True,
        ))
        if not self.marketplaces:
            raise serializers.ValidationError({"marketplaces": "Enable a Kaufland marketplace for order downloads."})

    def _get(self, path, params=None):
        url = f"{BASE_URL}{path}"
        if params:
            url = f"{url}?{urlencode(params, doseq=True)}"
        timestamp = int(timezone.now().timestamp())
        headers = {
            "Accept": "application/json",
            "Shop-Client-Key": self.client_key,
            "Shop-Timestamp": str(timestamp),
            "Shop-Signature": sign_request("GET", url, "", timestamp, self.client_secret),
            "User-Agent": "ChannelProManager/1.0",
        }
        try:
            response = self.client.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ProviderRequestError("Kaufland order request failed.") from exc

    def download_orders(self, *, updated_after=None):
        if updated_after is not None and timezone.is_naive(updated_after):
            updated_after = timezone.make_aware(updated_after)
        totals = dict.fromkeys(OrderSyncResult().as_dict(), 0)
        synced_at = timezone.now()
        for mapping in self.marketplaces:
            storefront = mapping.marketplace.external_marketplace_id or mapping.marketplace.country_code.lower()
            cursor = updated_after or (mapping.last_orders_sync_at - timedelta(minutes=10) if mapping.last_orders_sync_at else synced_at - timedelta(days=14))
            offset = 0
            limit = 100
            while True:
                payload = self._get("/orders", {
                    "limit": limit, "offset": offset, "storefront": storefront,
                    "ts_units_updated_from_iso": cursor.isoformat().replace("+00:00", "Z"),
                    "fulfillment_type": ["fulfilled_by_merchant", "fulfilled_by_kaufland"],
                })
                entries = payload.get("data") or []
                for summary in entries:
                    external_id = str(summary["id_order"])
                    details = self._get(f"/orders/{external_id}").get("data") or {}
                    result = self._save_order(details, mapping.marketplace)
                    for key, value in result.items():
                        totals[key] += value
                offset += len(entries)
                pagination = payload.get("pagination") or {}
                if not entries or offset >= int(pagination.get("total") or offset):
                    break
            mapping.last_orders_sync_at = synced_at
            mapping.save(update_fields=("last_orders_sync_at", "updated_at"))
        self.channel.last_sync_at = synced_at
        self.channel.save(update_fields=("last_sync_at", "updated_at"))
        return OrderSyncResult(**totals)

    @transaction.atomic
    def _save_order(self, data, marketplace):
        external_id = str(data["id_order"])
        units = data.get("order_units") or []
        shipping = data.get("shipping_address") or {}
        buyer = data.get("buyer") or {}
        created_at = parse_datetime(data.get("ts_created_iso") or "")
        updated_at = parse_datetime(data.get("ts_units_updated_iso") or "")
        currency = next((item.get("currency") for item in units if item.get("currency")), None) or marketplace.currency_code or "EUR"
        order, created = Order.objects.update_or_create(
            channel=self.channel, external_order_id=external_id,
            defaults={
                "customer": self.channel.customer, "marketplace": marketplace, "order_number": external_id,
                "status": order_status(units), "external_status": ", ".join(sorted({str(item.get("status")) for item in units if item.get("status")})),
                "fulfillment_channel": units[0].get("fulfillment_type") or "" if units else "",
                "sales_channel": f"Kaufland {marketplace.country_code}",
                "total": sum((cents(item.get("price")) + cents(item.get("shipping_rate")) for item in units), Decimal("0")),
                "currency": currency, "number_of_items_shipped": sum(item.get("status") == "sent" for item in units),
                "number_of_items_unshipped": sum(item.get("status") not in {"sent", "cancelled"} for item in units),
                "buyer_email": buyer.get("email") or "", "buyer_name": " ".join(filter(None, (shipping.get("first_name"), shipping.get("last_name")))),
                "shipping_address": shipping, "purchase_date": created_at, "last_update_date": updated_at,
                "imported_at": timezone.now(), "raw_data": data,
            },
        )
        items_created = items_updated = 0
        for unit in units:
            sku = str(unit.get("id_offer") or "")
            product = Product.objects.filter(customer=self.channel.customer, sku__iexact=sku).first() if sku else None
            _, item_created = OrderItem.objects.update_or_create(
                order=order, external_item_id=str(unit["id_order_unit"]),
                defaults={
                    "product": product, "sku": sku, "title": (unit.get("product") or {}).get("title") or "",
                    "quantity_ordered": 1, "quantity_shipped": int(unit.get("status") == "sent"),
                    "item_price": cents(unit.get("price")), "shipping_price": cents(unit.get("shipping_rate")),
                    "currency": unit.get("currency") or currency, "raw_data": unit,
                },
            )
            items_created += int(item_created)
            items_updated += int(not item_created)
        return {"orders_created": int(created), "orders_updated": int(not created), "items_created": items_created, "items_updated": items_updated}
