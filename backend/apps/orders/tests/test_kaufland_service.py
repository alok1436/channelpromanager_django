import base64
from decimal import Decimal
from unittest.mock import Mock

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.channels.models import Channel, ChannelMarketplace, KauflandChannelCredential, Marketplace
from apps.channels.services.encryption import encrypt_secret
from apps.companies.models import Company
from apps.customers.models import Customer
from apps.orders.models import Order, OrderItem
from apps.orders.services.kaufland import KauflandOrderService, sign_request
from apps.platforms.models import Platform
from apps.users.models import User


@override_settings(CHANNEL_ENCRYPTION_KEY=base64.urlsafe_b64encode(b"0" * 32).decode())
class KauflandOrderServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_platforms", verbosity=0)
        call_command("seed_marketplaces", verbosity=0)
        user = User.objects.create_user("kaufland-orders@example.com", "StrongPass123!")
        customer = Customer.objects.create(user=user, first_name="Kaufland", last_name="Seller", email="seller@example.com")
        company = Company.objects.create(customer=customer, name="Kaufland Seller")
        cls.channel = Channel.objects.create(
            customer=customer, company=company, platform=Platform.objects.get(code="kaufland"),
            name="Kaufland DE", country_code="DE",
        )
        ChannelMarketplace.objects.create(channel=cls.channel, marketplace=Marketplace.objects.get(code="kaufland_de"))
        KauflandChannelCredential.objects.create(
            channel=cls.channel, client_key=encrypt_secret("key"), client_secret=encrypt_secret("secret"),
        )

    def test_signed_request_uses_exact_url_and_timestamp(self):
        client = Mock()
        client.get.return_value.json.return_value = {"data": []}
        service = KauflandOrderService(self.channel, client=client)
        service._get("/orders", {"storefront": "de"})
        url = client.get.call_args.args[0]
        headers = client.get.call_args.kwargs["headers"]
        self.assertEqual(headers["Shop-Client-Key"], "key")
        self.assertEqual(headers["Shop-Signature"], sign_request("GET", url, "", headers["Shop-Timestamp"], "secret"))

    def test_order_and_units_are_upserted_without_duplicates(self):
        service = KauflandOrderService(self.channel)
        unit = {
            "id_order_unit": 123, "id_offer": "SKU-1", "status": "need_to_be_sent",
            "price": 1999, "shipping_rate": 400, "currency": "EUR", "product": {"title": "Test product"},
        }
        detail = {
            "id_order": "ORDER-1", "ts_created_iso": "2026-09-21T10:00:00Z",
            "buyer": {"email": "buyer@example.com"}, "order_units": [unit],
        }
        service._get = lambda path, params=None: {"data": [detail]} if path == "/orders" else {"data": detail}
        first = service.download_orders()
        unit["status"] = "sent"
        second = service.download_orders()
        self.assertEqual(first.orders_created, 1)
        self.assertEqual(second.orders_updated, 1)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(OrderItem.objects.count(), 1)
        self.assertEqual(Order.objects.get().total, Decimal("23.99"))
        self.assertEqual(Order.objects.get().status, Order.Status.COMPLETED)
