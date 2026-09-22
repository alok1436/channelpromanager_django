from django.core.management import call_command
from django.test import TestCase
from unittest.mock import patch
from rest_framework.test import APIClient

from apps.channels.models import Channel
from apps.companies.models import Company
from apps.customers.models import Customer, CustomerMembership
from apps.orders.models import Order
from apps.platforms.models import Platform
from apps.users.models import User


class OrderAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_permissions", verbosity=0)
        call_command("seed_platforms", verbosity=0)
        cls.user_a = User.objects.create_user("order-owner-a@example.com", "StrongPass123!")
        cls.user_b = User.objects.create_user("order-owner-b@example.com", "StrongPass123!")
        cls.customer_a = Customer.objects.create(user=cls.user_a, first_name="Order", last_name="A", email="order-a@example.com")
        cls.customer_b = Customer.objects.create(user=cls.user_b, first_name="Order", last_name="B", email="order-b@example.com")
        CustomerMembership.objects.create(customer=cls.customer_a, user=cls.user_a, is_owner=True)
        CustomerMembership.objects.create(customer=cls.customer_b, user=cls.user_b, is_owner=True)
        cls.other_order = Order.objects.create(customer=cls.customer_b, order_number="OTHER", total="5.00")
        company = Company.objects.create(customer=cls.customer_a, name="Order Company")
        cls.channel = Channel.objects.create(customer=cls.customer_a, company=company, platform=Platform.objects.get(code="kaufland"), name="Kaufland", country_code="DE")

    def setUp(self):
        self.client = APIClient()
        self.client.force_authenticate(self.user_a)

    def test_order_crud_is_tenant_scoped(self):
        created = self.client.post("/api/v1/orders/", {"order_number": "MANUAL-1", "status": "pending", "total": "12.50", "currency": "EUR"}, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        order_id = created.data["id"]
        self.assertEqual(Order.objects.get(pk=order_id).customer, self.customer_a)
        self.assertEqual([row["id"] for row in self.client.get("/api/v1/orders/").data["results"]], [order_id])
        changed = self.client.patch(f"/api/v1/orders/{order_id}/", {"status": "processing"}, format="json")
        self.assertEqual(changed.status_code, 200, changed.data)
        self.assertEqual(changed.data["status"], "processing")
        self.assertEqual(self.client.patch(f"/api/v1/orders/{order_id}/", {"customer_id": self.customer_b.id}, format="json").status_code, 200)
        self.assertEqual(Order.objects.get(pk=order_id).customer, self.customer_a)
        self.assertEqual(self.client.get(f"/api/v1/orders/{self.other_order.id}/").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/v1/orders/{order_id}/").status_code, 204)
        self.assertFalse(Order.objects.filter(pk=order_id).exists())

    @patch("apps.orders.services.get_order_service")
    def test_kaufland_sync_action_returns_counts(self, service_factory):
        service_factory.return_value.download_orders.return_value.as_dict.return_value = {
            "orders_created": 2, "orders_updated": 1, "items_created": 3, "items_updated": 0,
        }
        response = self.client.post(f"/api/v1/channels/{self.channel.id}/sync-orders/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["orders_created"], 2)
        service_factory.assert_called_once()
