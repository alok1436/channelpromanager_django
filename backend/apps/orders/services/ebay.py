from rest_framework import serializers

from .base import BaseOrderService


class EbayOrderService(BaseOrderService):
    """Platform boundary for the future eBay Fulfillment API importer."""

    def download_orders(self, *, updated_after=None):
        raise serializers.ValidationError({"platform": "eBay order import is not implemented yet."})
