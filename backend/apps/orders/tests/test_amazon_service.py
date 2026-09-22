import base64
from types import SimpleNamespace

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.channels.models import AmazonChannelCredential, Channel, ChannelMarketplace, Marketplace
from apps.channels.services.customer_settings import save_provider_setting
from apps.channels.services.encryption import encrypt_secret
from apps.companies.models import Company
from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem
from apps.orders.services.amazon import AmazonOrderService
from apps.platforms.models import Platform
from apps.users.models import User


@override_settings(CHANNEL_ENCRYPTION_KEY=base64.urlsafe_b64encode(b"0" * 32).decode())
class AmazonOrderServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_platforms", verbosity=0)
        call_command("seed_marketplaces", verbosity=0)
        user = User.objects.create_user("amazon-orders@example.com", "StrongPass123!")
        customer = Customer.objects.create(user=user, first_name="Amazon", last_name="Seller", email="seller@example.com")
        company = Company.objects.create(customer=customer, name="Amazon Seller")
        amazon = Platform.objects.get(code="amazon")
        cls.marketplace = Marketplace.objects.get(code="amazon_de")
        cls.channel = Channel.objects.create(customer=customer, company=company, platform=amazon, name="Amazon DE", country_code="DE")
        ChannelMarketplace.objects.create(channel=cls.channel, marketplace=cls.marketplace)
        AmazonChannelCredential.objects.create(channel=cls.channel, seller_id="seller", refresh_token=encrypt_secret("refresh-token"))
        save_provider_setting(customer, "amazon", {
            "lwa_client_id": "lwa-client-id", "lwa_client_secret": "lwa-secret",
            "spapi_application_id": "sp-api-app-id", "oauth_callback_url": "https://example.com/amazon/callback/",
        })

    def test_import_is_idempotent_and_updates_items(self):
        order_payload = {
            "AmazonOrderId": "123-1234567-1234567", "MarketplaceId": self.marketplace.external_marketplace_id,
            "OrderStatus": "Unshipped", "FulfillmentChannel": "MFN", "PurchaseDate": "2026-09-15T10:00:00Z",
            "LastUpdateDate": "2026-09-15T10:05:00Z", "OrderTotal": {"Amount": "25.50", "CurrencyCode": "EUR"},
            "NumberOfItemsShipped": 0, "NumberOfItemsUnshipped": 2,
        }
        item_payload = {
            "OrderItemId": "item-1", "SellerSKU": "SKU-1", "ASIN": "B000TEST",
            "Title": "Test item", "QuantityOrdered": 2, "QuantityShipped": 0,
            "ItemPrice": {"Amount": "25.50", "CurrencyCode": "EUR"},
        }
        service = AmazonOrderService(self.channel)
        service._request = lambda operation, **kwargs: {"payload": {"OrderItems": [item_payload]}} if operation == "get_order_items" else {"payload": {"Orders": [order_payload]}}

        first = service.download_orders()
        item_payload["QuantityShipped"] = 2
        second = service.download_orders()

        self.assertEqual(first.orders_created, 1)
        self.assertEqual(second.orders_updated, 1)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)
        self.assertEqual(OrderItem.objects.get().quantity_shipped, 2)

    def test_requests_are_dispatched_through_python_amazon_sp_api(self):
        service = AmazonOrderService(self.channel)
        response = SimpleNamespace(payload="sdk-payload")

        class FakeOrdersAPI:
            def get_orders(self, **kwargs):
                self.kwargs = kwargs
                return response

        fake_api = FakeOrdersAPI()
        service.orders_api = fake_api

        result = service._request("get_orders", MarketplaceIds=[self.marketplace.external_marketplace_id])

        self.assertEqual(result, {"payload": "sdk-payload"})
        self.assertEqual(fake_api.kwargs["MarketplaceIds"], [self.marketplace.external_marketplace_id])
