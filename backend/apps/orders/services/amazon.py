from datetime import timedelta, timezone as datetime_timezone
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from httpx import HTTPError as HttpxHTTPError
from rest_framework import serializers

from sp_api.api import OrdersV0
from sp_api.auth.exceptions import AuthorizationError
from sp_api.base import Marketplaces, SellingApiException

from apps.channels.models import AmazonChannelCredential
from apps.channels.services.customer_settings import decrypted_provider_setting
from apps.channels.services.encryption import decrypt_secret
from apps.channels.services.http import ProviderRequestError
from apps.orders.models import Order, OrderItem
from apps.products.models import Product
from .base import BaseOrderService, OrderSyncResult


def _money(value):
    try:
        return Decimal(str((value or {}).get("Amount") or "0"))
    except (InvalidOperation, TypeError):
        return Decimal("0")


def _date(value):
    return parse_datetime(value) if value else None


def _status(value):
    return {
        "Pending": Order.Status.PENDING, "PendingAvailability": Order.Status.PENDING,
        "Unshipped": Order.Status.PROCESSING, "PartiallyShipped": Order.Status.PROCESSING,
        "InvoiceUnconfirmed": Order.Status.PROCESSING, "Shipped": Order.Status.COMPLETED,
        "Canceled": Order.Status.CANCELLED, "Unfulfillable": Order.Status.CANCELLED,
    }.get(value, Order.Status.PROCESSING)


class AmazonOrderService(BaseOrderService):
    """Imports Amazon Orders API v0 data without mixing provider details into views."""

    def __init__(self, channel, *, timeout=30):
        super().__init__(channel)
        if channel.platform.code != "amazon":
            raise serializers.ValidationError({"platform": "Channel is not an Amazon channel."})
        self.timeout = timeout
        self.marketplace_mappings = self._enabled_marketplaces()
        marketplace_code = self.marketplace_mappings[0].marketplace.country_code.upper()
        try:
            marketplace = Marketplaces[marketplace_code]
        except KeyError as exc:
            raise serializers.ValidationError({"marketplaces": f"Unsupported Amazon marketplace: {marketplace_code}."}) from exc
        credential = AmazonChannelCredential.objects.filter(channel=channel).first()
        if credential is None:
            raise serializers.ValidationError({"credentials": "Amazon channel credentials are not configured."})
        _, app_credentials = decrypted_provider_setting(channel.customer, "amazon")
        self.orders_api = OrdersV0(
            marketplace=marketplace,
            refresh_token=decrypt_secret(credential.refresh_token),
            credentials={
                "lwa_app_id": app_credentials["lwa_client_id"],
                "lwa_client_secret": app_credentials["lwa_client_secret"],
            },
            timeout=timeout,
        )

    def _enabled_marketplaces(self):
        rows = list(self.channel.channel_marketplaces.select_related("marketplace").filter(
            is_enabled=True, orders_enabled=True, marketplace__is_active=True,
        ))
        if not rows:
            raise serializers.ValidationError({"marketplaces": "Enable at least one marketplace for order downloads."})
        endpoints = set()
        for row in rows:
            try:
                endpoints.add(Marketplaces[row.marketplace.country_code.upper()].endpoint)
            except KeyError as exc:
                raise serializers.ValidationError({"marketplaces": f"Unsupported Amazon marketplace: {row.marketplace.country_code}."}) from exc
        if len(endpoints) != 1:
            raise serializers.ValidationError({"marketplaces": "Amazon marketplaces in one channel must share an SP-API endpoint."})
        return rows

    def _request(self, operation, **kwargs):
        try:
            if operation == "get_order_items":
                response = self.orders_api.get_order_items(kwargs.pop("order_id"), **kwargs)
            else:
                response = getattr(self.orders_api, operation)(**kwargs)
            return {"payload": response.payload}
        except (SellingApiException, AuthorizationError, HttpxHTTPError, TimeoutError) as exc:
            raise ProviderRequestError("Amazon SP-API order request failed.") from exc

    def download_orders(self, *, updated_after=None):
        external_ids = [row.marketplace.external_marketplace_id for row in self.marketplace_mappings]
        marketplaces = {row.marketplace.external_marketplace_id: row.marketplace for row in self.marketplace_mappings}
        if updated_after is None:
            previous = [row.last_orders_sync_at for row in self.marketplace_mappings if row.last_orders_sync_at]
            updated_after = min(previous) - timedelta(minutes=5) if previous else timezone.now() - timedelta(days=14)
        elif timezone.is_naive(updated_after):
            updated_after = timezone.make_aware(updated_after, timezone.get_current_timezone())
        last_updated_after = updated_after.astimezone(datetime_timezone.utc).isoformat().replace("+00:00", "Z")
        next_token = None
        totals = dict.fromkeys(OrderSyncResult().as_dict(), 0)
        while True:
            response = self._request(
                "get_orders", MarketplaceIds=external_ids, LastUpdatedAfter=last_updated_after,
                MaxResultsPerPage=100, **({"NextToken": next_token} if next_token else {}),
            )
            payload = response.get("payload") or {}
            for data in payload.get("Orders") or []:
                result = self._save_order(data, marketplaces.get(data.get("MarketplaceId")))
                for key, value in result.items():
                    totals[key] += value
            next_token = payload.get("NextToken")
            if not next_token:
                break
        synced_at = timezone.now()
        self.channel.channel_marketplaces.filter(pk__in=[row.pk for row in self.marketplace_mappings]).update(last_orders_sync_at=synced_at)
        self.channel.last_sync_at = synced_at
        self.channel.save(update_fields=("last_sync_at", "updated_at"))
        return OrderSyncResult(**totals)

    @transaction.atomic
    def _save_order(self, data, marketplace):
        external_id = data["AmazonOrderId"]
        total = data.get("OrderTotal") or {}
        buyer = data.get("BuyerInfo") or {}
        order, created = Order.objects.update_or_create(
            channel=self.channel, external_order_id=external_id,
            defaults={
                "customer": self.channel.customer, "marketplace": marketplace, "order_number": external_id,
                "seller_order_id": data.get("SellerOrderId") or "", "status": _status(data.get("OrderStatus")),
                "external_status": data.get("OrderStatus") or "", "fulfillment_channel": data.get("FulfillmentChannel") or "",
                "sales_channel": data.get("SalesChannel") or "", "ship_service_level": data.get("ShipServiceLevel") or "",
                "total": _money(total), "currency": total.get("CurrencyCode") or (marketplace.currency_code if marketplace else "USD"),
                "number_of_items_shipped": data.get("NumberOfItemsShipped") or 0,
                "number_of_items_unshipped": data.get("NumberOfItemsUnshipped") or 0,
                "buyer_email": buyer.get("BuyerEmail") or "", "buyer_name": buyer.get("BuyerName") or "",
                "shipping_address": data.get("ShippingAddress") or {}, "purchase_date": _date(data.get("PurchaseDate")),
                "last_update_date": _date(data.get("LastUpdateDate")), "earliest_ship_date": _date(data.get("EarliestShipDate")),
                "latest_ship_date": _date(data.get("LatestShipDate")), "imported_at": timezone.now(), "raw_data": data,
            },
        )
        items_created, items_updated = self._save_items(order)
        return {"orders_created": int(created), "orders_updated": int(not created), "items_created": items_created, "items_updated": items_updated}

    def _save_items(self, order):
        created_count = updated_count = 0
        next_token = None
        while True:
            response = self._request(
                "get_order_items", order_id=order.external_order_id,
                **({"NextToken": next_token} if next_token else {}),
            )
            payload = response.get("payload") or {}
            for data in payload.get("OrderItems") or []:
                sku, price = data.get("SellerSKU") or "", data.get("ItemPrice") or {}
                product = Product.objects.filter(customer=self.channel.customer, sku__iexact=sku).first() if sku else None
                _, created = OrderItem.objects.update_or_create(
                    order=order, external_item_id=data["OrderItemId"],
                    defaults={
                        "product": product, "sku": sku, "asin": data.get("ASIN") or "", "title": data.get("Title") or "",
                        "quantity_ordered": data.get("QuantityOrdered") or 0, "quantity_shipped": data.get("QuantityShipped") or 0,
                        "item_price": _money(price), "item_tax": _money(data.get("ItemTax")),
                        "shipping_price": _money(data.get("ShippingPrice")), "shipping_tax": _money(data.get("ShippingTax")),
                        "promotion_discount": _money(data.get("PromotionDiscount")), "currency": price.get("CurrencyCode") or order.currency,
                        "condition_id": data.get("ConditionId") or "", "condition_subtype_id": data.get("ConditionSubtypeId") or "",
                        "raw_data": data,
                    },
                )
                created_count += int(created)
                updated_count += int(not created)
            next_token = payload.get("NextToken")
            if not next_token:
                return created_count, updated_count
