import base64
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.channels.models import CdiscountChannelCredential, Channel, ChannelMarketplace
from apps.companies.models import Company
from apps.customers.models import Customer, CustomerMembership
from apps.permissions.models import Permission
from apps.roles.models import Role, RolePermission
from apps.users.models import User
from apps.channels.services.customer_settings import save_provider_setting


ENCRYPTION_KEY = base64.urlsafe_b64encode(b"0" * 32).decode()


@override_settings(CHANNEL_ENCRYPTION_KEY=ENCRYPTION_KEY)
class ChannelAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_permissions", verbosity=0)
        call_command("seed_platforms", verbosity=0)
        call_command("seed_marketplaces", verbosity=0)
        from apps.platforms.models import Platform
        from apps.channels.models import Marketplace

        cls.amazon = Platform.objects.get(code="amazon")
        cls.ebay = Platform.objects.get(code="ebay")
        cls.cdiscount = Platform.objects.get(code="cdiscount")
        cls.woocommerce = Platform.objects.get(code="woocommerce")
        cls.amazon_de = Marketplace.objects.get(code="amazon_de")
        cls.ebay_de = Marketplace.objects.get(code="ebay_de")

        cls.owner_a = User.objects.create_user("channel-owner-a@example.com", "StrongPass123!")
        cls.owner_b = User.objects.create_user("channel-owner-b@example.com", "StrongPass123!")
        cls.staff_view = User.objects.create_user("channel-staff-view@example.com", "StrongPass123!")
        cls.staff_update = User.objects.create_user("channel-staff-update@example.com", "StrongPass123!")
        cls.staff_all = User.objects.create_user("channel-staff-all@example.com", "StrongPass123!")
        cls.superuser = User.objects.create_superuser("channel-admin@example.com", "StrongPass123!")
        cls.customer_a = Customer.objects.create(user=cls.owner_a, first_name="A", last_name="Owner", email="channel-a@example.com")
        cls.customer_b = Customer.objects.create(user=cls.owner_b, first_name="B", last_name="Owner", email="channel-b@example.com")
        save_provider_setting(cls.customer_a, "amazon", {
            "lwa_client_id": "client-id", "lwa_client_secret": "client-secret",
            "spapi_application_id": "app-id",
            "authorization_url": "https://sellercentral-europe.amazon.com/apps/authorize/consent",
            "oauth_callback_url": "https://app.example.com/api/v1/channels/amazon/callback/",
        })
        CustomerMembership.objects.create(customer=cls.customer_a, user=cls.owner_a, is_owner=True)
        CustomerMembership.objects.create(customer=cls.customer_b, user=cls.owner_b, is_owner=True)
        cls.company_a = Company.objects.create(customer=cls.customer_a, name="Channel Company A")
        cls.company_b = Company.objects.create(customer=cls.customer_b, name="Channel Company B")

        view_role = Role.objects.create(customer=cls.customer_a, name="Channel Viewer", slug="channel-viewer")
        RolePermission.objects.create(role=view_role, permission=Permission.objects.get(codename="channels.view"))
        CustomerMembership.objects.create(customer=cls.customer_a, user=cls.staff_view, role=view_role)

        update_role = Role.objects.create(customer=cls.customer_a, name="Channel Editor", slug="channel-editor")
        for code in ("channels.view", "channels.update"):
            RolePermission.objects.create(role=update_role, permission=Permission.objects.get(codename=code))
        CustomerMembership.objects.create(customer=cls.customer_a, user=cls.staff_update, role=update_role)

        all_role = Role.objects.create(customer=cls.customer_a, name="Channel Admin", slug="channel-admin")
        for permission in Permission.objects.filter(codename__startswith="channels."):
            RolePermission.objects.create(role=all_role, permission=permission)
        CustomerMembership.objects.create(customer=cls.customer_a, user=cls.staff_all, role=all_role)

        cls.channel_a = Channel.objects.create(
            customer=cls.customer_a, company=cls.company_a, platform=cls.amazon,
            name="Amazon A", country_code="DE", created_by=cls.owner_a, updated_by=cls.owner_a,
        )
        cls.channel_b = Channel.objects.create(
            customer=cls.customer_b, company=cls.company_b, platform=cls.amazon,
            name="Amazon B", country_code="DE", created_by=cls.owner_b, updated_by=cls.owner_b,
        )

    def setUp(self):
        self.client = APIClient()

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def test_anonymous_list_is_unauthorized(self):
        self.assertEqual(self.client.get("/api/v1/channels/").status_code, 401)

    def test_owner_list_and_detail_are_tenant_scoped(self):
        self.authenticate(self.owner_a)
        response = self.client.get("/api/v1/channels/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data["results"]], [self.channel_a.id])
        self.assertEqual(self.client.get(f"/api/v1/channels/{self.channel_b.id}/").status_code, 404)

    def test_cross_tenant_update_delete_credentials_and_marketplaces_are_hidden(self):
        self.authenticate(self.staff_all)
        url = f"/api/v1/channels/{self.channel_b.id}"
        self.assertEqual(self.client.patch(f"{url}/", {"name": "Taken"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(f"{url}/").status_code, 404)
        self.assertEqual(self.client.post(f"{url}/disconnect/").status_code, 404)
        self.assertEqual(self.client.patch(f"{url}/credentials/", {"refresh_token": "x"}, format="json").status_code, 404)
        self.assertEqual(self.client.put(f"{url}/marketplaces/", {"marketplace_ids": []}, format="json").status_code, 404)
        self.channel_b.refresh_from_db()
        self.assertEqual(self.channel_b.name, "Amazon B")
        self.assertTrue(self.channel_b.is_active)

    def test_create_assigns_customer_validates_company_and_normalizes_fields(self):
        self.authenticate(self.owner_a)
        response = self.client.post("/api/v1/channels/", {
            "company_id": self.company_a.id, "platform": "amazon", "name": "Amazon New",
            "country_code": "de", "standard_shipping_cost": "4.99",
            "marketplace_ids": [self.amazon_de.id],
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        channel = Channel.objects.get(pk=response.data["id"])
        self.assertEqual(channel.customer, self.customer_a)
        self.assertEqual(channel.created_by, self.owner_a)
        self.assertEqual(channel.country_code, "DE")
        self.assertEqual(ChannelMarketplace.objects.get(channel=channel).marketplace, self.amazon_de)
        self.assertNotIn("customer", response.data)

        denied = self.client.post("/api/v1/channels/", {
            "company_id": self.company_b.id, "platform": "amazon", "name": "Wrong Company", "country_code": "DE"
        }, format="json")
        self.assertEqual(denied.status_code, 400)
        self.assertFalse(Channel.objects.filter(name="Wrong Company").exists())

    def test_duplicate_name_and_negative_shipping_cost_are_rejected(self):
        self.authenticate(self.owner_a)
        duplicate = self.client.post("/api/v1/channels/", {
            "company_id": self.company_a.id, "platform": "amazon", "name": "amazon a", "country_code": "DE"
        }, format="json")
        self.assertEqual(duplicate.status_code, 400)
        negative = self.client.post("/api/v1/channels/", {
            "company_id": self.company_a.id, "platform": "amazon", "name": "Negative", "country_code": "DE",
            "standard_shipping_cost": "-1.00",
        }, format="json")
        self.assertEqual(negative.status_code, 400)

    def test_same_name_is_allowed_for_different_customers(self):
        self.authenticate(self.owner_b)
        response = self.client.post("/api/v1/channels/", {
            "company_id": self.company_b.id, "platform": "amazon", "name": "Amazon A", "country_code": "DE"
        }, format="json")
        self.assertEqual(response.status_code, 201, response.data)

    def test_staff_permissions_share_customer_data(self):
        self.authenticate(self.staff_view)
        self.assertEqual(self.client.get("/api/v1/channels/").status_code, 200)
        self.assertEqual(self.client.patch(f"/api/v1/channels/{self.channel_a.id}/", {"note": "denied"}, format="json").status_code, 403)
        self.authenticate(self.staff_update)
        response = self.client.patch(f"/api/v1/channels/{self.channel_a.id}/", {"note": "shared update"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.channel_a.refresh_from_db()
        self.assertEqual(self.channel_a.note, "shared update")
        self.assertEqual(self.channel_a.updated_by, self.staff_update)

    def test_marketplace_platform_must_match(self):
        self.authenticate(self.owner_a)
        denied = self.client.put(f"/api/v1/channels/{self.channel_a.id}/marketplaces/", {
            "marketplace_ids": [self.ebay_de.id]
        }, format="json")
        self.assertEqual(denied.status_code, 400)
        accepted = self.client.put(f"/api/v1/channels/{self.channel_a.id}/marketplaces/", {
            "marketplace_ids": [self.amazon_de.id]
        }, format="json")
        self.assertEqual(accepted.status_code, 200, accepted.data)

    def test_credentials_are_platform_specific_encrypted_and_never_serialized(self):
        self.authenticate(self.owner_a)
        created = self.client.post("/api/v1/channels/", {
            "company_id": self.company_a.id, "platform": "cdiscount", "name": "CD France",
            "country_code": "FR", "credentials": {
                "seller_id": "seller-1", "client_id": "client-1", "client_secret": "secret-1"
            },
        }, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        serialized = str(created.data)
        for secret in ("client-1", "secret-1", "client_secret"):
            self.assertNotIn(secret, serialized)
        credential = CdiscountChannelCredential.objects.get(channel_id=created.data["id"])
        self.assertNotEqual(credential.client_id, "client-1")
        self.assertNotEqual(credential.client_secret, "secret-1")
        wrong = self.client.patch(f"/api/v1/channels/{created.data['id']}/credentials/", {
            "consumer_key": "ck_bad", "consumer_secret": "cs_bad"
        }, format="json")
        self.assertEqual(wrong.status_code, 400)
        status_response = self.client.get(f"/api/v1/channels/{created.data['id']}/credentials/status/")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.data["credential_status"], "configured")
        self.assertNotIn("client_secret", status_response.data)

    def test_woocommerce_requires_https_and_never_returns_consumer_secrets(self):
        self.authenticate(self.owner_a)
        denied = self.client.post("/api/v1/channels/", {
            "company_id": self.company_a.id, "platform": "woocommerce", "name": "WC Bad", "country_code": "DE",
            "credentials": {"store_url": "http://shop.example.com", "consumer_key": "ck", "consumer_secret": "cs"},
        }, format="json")
        self.assertEqual(denied.status_code, 400)
        accepted = self.client.post("/api/v1/channels/", {
            "company_id": self.company_a.id, "platform": "woocommerce", "name": "WC Good", "country_code": "DE",
            "credentials": {"store_url": "https://SHOP.example.com/", "consumer_key": "ck", "consumer_secret": "cs"},
        }, format="json")
        self.assertEqual(accepted.status_code, 201, accepted.data)
        status_response = self.client.get(f"/api/v1/channels/{accepted.data['id']}/credentials/status/")
        self.assertEqual(status_response.data["store_url"], "https://shop.example.com")
        self.assertNotIn("consumer_key", status_response.data)
        self.assertNotIn("consumer_secret", status_response.data)

    @patch("apps.channels.services.amazon_service.post_form")
    def test_amazon_oauth_state_is_single_use_and_tokens_are_not_exposed(self, post_form_mock):
        post_form_mock.return_value = {"refresh_token": "refresh-value", "access_token": "access-value", "expires_in": 3600}
        self.authenticate(self.owner_a)
        authorize = self.client.post(f"/api/v1/channels/{self.channel_a.id}/authorize/")
        self.assertEqual(authorize.status_code, 200, authorize.data)
        from urllib.parse import parse_qs, urlsplit
        state = parse_qs(urlsplit(authorize.data["authorization_url"]).query)["state"][0]
        self.client.force_authenticate(user=None)
        callback = self.client.get("/api/v1/channels/amazon/callback/", {
            "state": state, "spapi_oauth_code": "auth-code", "selling_partner_id": "seller-1",
        })
        self.assertEqual(callback.status_code, 200, callback.data)
        self.assertNotIn("refresh", str(callback.data))
        replay = self.client.get("/api/v1/channels/amazon/callback/", {
            "state": state, "spapi_oauth_code": "auth-code", "selling_partner_id": "seller-1",
        })
        self.assertEqual(replay.status_code, 400)

    def test_authenticated_platform_and_marketplace_discovery(self):
        self.authenticate(self.owner_a)
        self.assertEqual(self.client.get("/api/v1/platforms/").status_code, 200)
        response = self.client.get("/api/v1/platforms/amazon/marketplaces/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("A1PA6795UKMFR9", [row["external_marketplace_id"] for row in response.data])

    def test_marketplace_crud_is_superadmin_only(self):
        self.authenticate(self.owner_a)
        self.assertEqual(self.client.get("/api/v1/marketplaces/").status_code, 403)

        self.authenticate(self.superuser)
        created = self.client.post("/api/v1/marketplaces/", {
            "platform": self.amazon.id, "name": "Amazon Test", "code": "amazon_test",
            "country_code": "de", "currency_code": "eur", "external_marketplace_id": "TEST-ID",
            "region": "eu", "is_active": True,
        }, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["platform_name"], "Amazon")
        self.assertEqual(created.data["country_code"], "DE")
        updated = self.client.patch(f"/api/v1/marketplaces/{created.data['id']}/", {"name": "Amazon Updated"}, format="json")
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(self.client.delete(f"/api/v1/marketplaces/{created.data['id']}/").status_code, 204)

    def test_customer_channel_settings_are_tenant_scoped_and_secrets_are_write_only(self):
        self.authenticate(self.owner_a)
        response = self.client.get("/api/v1/channel-settings/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["amazon"]["lwa_client_id"], "client-id")
        self.assertNotIn("lwa_client_secret", response.data["amazon"])
        saved = self.client.patch("/api/v1/channel-settings/", {"ebay": {
            "client_id": "ebay-id", "client_secret": "ebay-secret", "redirect_uri": "ebay-runame",
            "authorization_url": "https://auth.ebay.com/oauth2/authorize",
            "oauth_callback_url": "https://app.example.com/api/v1/channels/ebay/callback/",
            "oauth_scopes": "https://api.ebay.com/oauth/api_scope",
        }}, format="json")
        self.assertEqual(saved.status_code, 200, saved.data)
        self.assertNotIn("client_secret", saved.data["ebay"])

        self.authenticate(self.owner_b)
        isolated = self.client.get("/api/v1/channel-settings/")
        self.assertFalse(isolated.data["amazon"]["configured"])
        self.assertFalse(isolated.data["ebay"]["configured"])
