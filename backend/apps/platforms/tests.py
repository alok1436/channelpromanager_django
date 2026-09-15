from django.test import TestCase
from rest_framework.test import APIClient

from apps.users.models import User
from .models import Platform


class PlatformAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("platform-admin@example.com", "StrongPass123!")
        cls.user = User.objects.create_user("platform-user@example.com", "StrongPass123!")

    def setUp(self):
        self.client = APIClient()

    def test_authenticated_users_can_read_but_only_superadmin_can_modify_platforms(self):
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get("/api/v1/platforms/").status_code, 200)
        self.assertEqual(self.client.post("/api/v1/platforms/", {"name": "Denied", "code": "denied"}).status_code, 403)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get("/api/v1/platforms/").status_code, 200)

    def test_seeded_platforms_exist(self):
        self.assertEqual(
            set(Platform.objects.values_list("code", flat=True)),
            {"amazon", "ebay", "otto", "cdiscount", "woocommerce"},
        )

    def test_superadmin_crud_normalizes_code_and_soft_deactivates(self):
        self.client.force_authenticate(self.admin)
        created = self.client.post("/api/v1/platforms/", {
            "name": "Shopify", "code": " SHOPIFY ",
            "description": "Commerce platform", "logo_url": "https://example.com/shopify.svg",
        }, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["code"], "shopify")
        platform_id = created.data["id"]
        updated = self.client.patch(f"/api/v1/platforms/{platform_id}/", {"name": "Shopify Plus"}, format="json")
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(self.client.delete(f"/api/v1/platforms/{platform_id}/").status_code, 204)
        self.assertFalse(Platform.objects.get(pk=platform_id).is_active)

    def test_duplicate_code_is_rejected_case_insensitively(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post("/api/v1/platforms/", {"name": "Duplicate", "code": "AMAZON"}, format="json")
        self.assertEqual(response.status_code, 400)
