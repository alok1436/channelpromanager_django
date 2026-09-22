from rest_framework import serializers


def get_order_service(channel):
    if channel.platform.code == "amazon":
        from .amazon import AmazonOrderService
        return AmazonOrderService(channel)
    if channel.platform.code == "ebay":
        from .ebay import EbayOrderService
        return EbayOrderService(channel)
    if channel.platform.code == "kaufland":
        from .kaufland import KauflandOrderService
        return KauflandOrderService(channel)
    raise serializers.ValidationError({"platform": f"Order import is not implemented for {channel.platform.code}."})
