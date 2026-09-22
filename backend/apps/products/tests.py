import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.companies.models import Company
from apps.customers.models import Customer, CustomerMembership
from apps.permissions.models import Permission
from apps.products.models import Product, ProductImage, ProductStatus, ProductTranslation, ProductVariant
from apps.roles.models import Role, RolePermission
from apps.users.models import User


TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="product-tests-")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ProductAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_permissions", verbosity=0)
        cls.owner_a = User.objects.create_user("product-owner-a@example.com", "StrongPass123!")
        cls.owner_b = User.objects.create_user("product-owner-b@example.com", "StrongPass123!")
        cls.viewer = User.objects.create_user("product-viewer@example.com", "StrongPass123!")
        cls.editor = User.objects.create_user("product-editor@example.com", "StrongPass123!")
        cls.customer_a = Customer.objects.create(user=cls.owner_a, first_name="Product", last_name="A", email="product-a@example.com")
        cls.customer_b = Customer.objects.create(user=cls.owner_b, first_name="Product", last_name="B", email="product-b@example.com")
        CustomerMembership.objects.create(customer=cls.customer_a, user=cls.owner_a, is_owner=True)
        CustomerMembership.objects.create(customer=cls.customer_b, user=cls.owner_b, is_owner=True)
        cls.company_a = Company.objects.create(customer=cls.customer_a, name="Product Company A")
        cls.company_b = Company.objects.create(customer=cls.customer_b, name="Product Company B")

        viewer_role = Role.objects.create(customer=cls.customer_a, name="Product Viewer", slug="product-viewer")
        RolePermission.objects.create(role=viewer_role, permission=Permission.objects.get(codename="products.view"))
        CustomerMembership.objects.create(customer=cls.customer_a, user=cls.viewer, role=viewer_role)
        editor_role = Role.objects.create(customer=cls.customer_a, name="Product Editor", slug="product-editor")
        for code in ("products.view", "products.update"):
            RolePermission.objects.create(role=editor_role, permission=Permission.objects.get(codename=code))
        CustomerMembership.objects.create(customer=cls.customer_a, user=cls.editor, role=editor_role)

        cls.product_a = Product.objects.create(customer=cls.customer_a, company=cls.company_a, sku="SKU-A", brand="Alpha", created_by=cls.owner_a, updated_by=cls.owner_a)
        cls.translation_a = ProductTranslation.objects.create(customer=cls.customer_a, product=cls.product_a, language_code="en", name="English Product")
        cls.product_b = Product.objects.create(customer=cls.customer_b, company=cls.company_b, sku="SKU-B", created_by=cls.owner_b, updated_by=cls.owner_b)
        cls.translation_b = ProductTranslation.objects.create(customer=cls.customer_b, product=cls.product_b, language_code="en", name="Secret Product")
        cls.variant_b = ProductVariant.objects.create(customer=cls.customer_b, product=cls.product_b, sku="VAR-B")

    def setUp(self):
        self.client = APIClient()

    def authenticate(self, user):
        self.client.force_authenticate(user)

    def create_payload(self, **overrides):
        payload = {
            "company_id": self.company_a.id, "sku": "sku-new", "brand": "Brand",
            "condition": "new", "standard_sale_price": "19.99", "currency_code": "eur",
            "status": "active", "translations": [{"language_code": "de_de", "name": "Produkt", "bullet_points": ["Leicht"]}],
            "variants": [{"sku": "var-new", "standard_sale_price": "21.00", "attributes": [{"name": "Color", "value": "Blue"}]}],
        }
        payload.update(overrides)
        return payload

    def test_anonymous_list_returns_401(self):
        self.assertEqual(self.client.get("/api/v1/products/").status_code, 401)

    def test_customer_product_languages_are_tenant_scoped_and_validated(self):
        url = "/api/v1/product-language-settings/"
        self.authenticate(self.owner_a)
        self.assertEqual(self.client.get(url).data["language_codes"], ["en"])
        updated = self.client.put(url, {"language_codes": ["en", "it"]}, format="json")
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data["language_codes"], ["en", "it"])
        self.assertEqual(self.client.put(url, {"language_codes": ["en", "EN"]}, format="json").status_code, 400)
        self.assertEqual(self.client.put(url, {"language_codes": []}, format="json").status_code, 400)
        self.authenticate(self.owner_b)
        self.assertEqual(self.client.get(url).data["language_codes"], ["en"])
        self.authenticate(self.viewer)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.put(url, {"language_codes": ["fr"]}, format="json").status_code, 403)

    def test_owner_list_detail_and_language_are_tenant_scoped(self):
        self.authenticate(self.owner_a)
        listed = self.client.get("/api/v1/products/?language=en")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual([row["id"] for row in listed.data["results"]], [self.product_a.id])
        self.assertEqual(listed.data["results"][0]["name"], "English Product")
        self.assertEqual(self.client.get(f"/api/v1/products/{self.product_b.id}/").status_code, 404)

    def test_create_assigns_customer_and_rejects_tenant_fields_and_foreign_company(self):
        self.authenticate(self.owner_a)
        created = self.client.post("/api/v1/products/", self.create_payload(), format="json")
        self.assertEqual(created.status_code, 201, created.data)
        product = Product.objects.get(pk=created.data["id"])
        self.assertEqual(product.customer, self.customer_a)
        self.assertEqual(product.sku, "SKU-NEW")
        self.assertEqual(product.translations.get().language_code, "de-DE")
        self.assertEqual(product.variants.get().sku, "VAR-NEW")
        self.assertNotIn("customer", created.data)
        foreign = self.client.post("/api/v1/products/", self.create_payload(sku="FOREIGN", company_id=self.company_b.id), format="json")
        self.assertEqual(foreign.status_code, 400)
        injected = self.client.post("/api/v1/products/", self.create_payload(sku="INJECTED", customer_id=self.customer_b.id), format="json")
        self.assertEqual(injected.status_code, 400)

    def test_product_sku_unique_per_customer(self):
        self.authenticate(self.owner_a)
        denied = self.client.post("/api/v1/products/", self.create_payload(sku=" sku-a ", variants=[]), format="json")
        self.assertEqual(denied.status_code, 400)
        self.authenticate(self.owner_b)
        allowed = self.client.post("/api/v1/products/", {
            "company_id": self.company_b.id, "sku": "SKU-A", "condition": "new",
            "translations": [{"language_code": "en", "name": "Allowed"}],
        }, format="json")
        self.assertEqual(allowed.status_code, 201, allowed.data)

    def test_cross_tenant_update_and_nested_resources_return_404(self):
        self.authenticate(self.owner_a)
        base = f"/api/v1/products/{self.product_b.id}"
        self.assertEqual(self.client.patch(f"{base}/", {"brand": "Stolen"}, format="json").status_code, 404)
        self.assertEqual(self.client.patch(f"{base}/translations/{self.translation_b.id}/", {"name": "Stolen"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(f"{base}/translations/{self.translation_b.id}/").status_code, 404)
        self.assertEqual(self.client.patch(f"{base}/variants/{self.variant_b.id}/", {"sku": "STOLEN"}, format="json").status_code, 404)
        self.assertEqual(self.client.delete(f"{base}/variants/{self.variant_b.id}/").status_code, 404)

    def test_translation_crud_and_uniqueness(self):
        self.authenticate(self.owner_a)
        base = f"/api/v1/products/{self.product_a.id}/translations"
        created = self.client.post(f"{base}/", {"language_code": "fr_fr", "name": "Produit", "bullet_points": ["Simple"]}, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        duplicate = self.client.post(f"{base}/", {"language_code": "fr-FR", "name": "Duplicate"}, format="json")
        self.assertEqual(duplicate.status_code, 400)
        updated = self.client.patch(f"{base}/{created.data['id']}/", {"name": "Produit modifié"}, format="json")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(self.client.delete(f"{base}/{created.data['id']}/").status_code, 204)

    def test_variant_crud_attributes_and_customer_sku_uniqueness(self):
        self.authenticate(self.owner_a)
        base = f"/api/v1/products/{self.product_a.id}/variants"
        created = self.client.post(f"{base}/", {"sku": "shirt-blue-m", "standard_sale_price": "29.99", "attributes": [{"name": "Color", "value": "Blue"}, {"name": "Size", "value": "M"}]}, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(len(created.data["attributes"]), 2)
        duplicate = self.client.post(f"{base}/", {"sku": "SHIRT-BLUE-M"}, format="json")
        self.assertEqual(duplicate.status_code, 400)
        updated = self.client.patch(f"{base}/{created.data['id']}/", {"attributes": [{"name": "Size", "value": "L"}]}, format="json")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.data["attributes"][0]["value"], "L")

    def test_image_crud_primary_and_reorder(self):
        self.authenticate(self.owner_a)
        base = f"/api/v1/products/{self.product_a.id}/images"
        first = self.client.post(f"{base}/", {"image": SimpleUploadedFile("one.gif", b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;", content_type="image/gif"), "alt_text": "One"}, format="multipart")
        self.assertEqual(first.status_code, 201, first.data)
        self.assertTrue(first.data["is_primary"])
        second = self.client.post(f"{base}/", {"image": SimpleUploadedFile("two.gif", b"GIF89a\x01\x00\x01\x00\x00\x00\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;", content_type="image/gif")}, format="multipart")
        promoted = self.client.patch(f"{base}/{second.data['id']}/", {"is_primary": True}, format="json")
        self.assertEqual(promoted.status_code, 200)
        self.assertEqual(ProductImage.objects.filter(product=self.product_a, is_primary=True).count(), 1)
        reordered = self.client.put(f"{base}/reorder/", {"image_ids": [second.data["id"], first.data["id"]]}, format="json")
        self.assertEqual(reordered.status_code, 200, reordered.data)
        self.assertEqual(self.client.delete(f"{base}/{second.data['id']}/").status_code, 204)
        self.assertTrue(ProductImage.objects.get(pk=first.data["id"]).is_primary)

    def test_archive_restore_duplicate_and_bulk_are_tenant_safe(self):
        self.authenticate(self.owner_a)
        archived = self.client.post(f"/api/v1/products/{self.product_a.id}/archive/")
        self.assertEqual(archived.status_code, 200)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.status, ProductStatus.ARCHIVED)
        self.assertFalse(self.product_a.is_active)
        self.assertEqual(self.client.post(f"/api/v1/products/{self.product_a.id}/restore/").status_code, 200)
        copied = self.client.post(f"/api/v1/products/{self.product_a.id}/duplicate/")
        self.assertEqual(copied.status_code, 201, copied.data)
        self.assertTrue(copied.data["sku"].startswith("SKU-A-COPY"))
        denied = self.client.post("/api/v1/products/bulk/status/", {"product_ids": [self.product_a.id, self.product_b.id], "status": "inactive"}, format="json")
        self.assertEqual(denied.status_code, 400)
        accepted = self.client.post("/api/v1/products/bulk/archive/", {"product_ids": [self.product_a.id, copied.data["id"]]}, format="json")
        self.assertEqual(accepted.status_code, 200)

    def test_staff_permissions_cover_customer_products_not_creator(self):
        self.authenticate(self.viewer)
        listed = self.client.get("/api/v1/products/")
        self.assertEqual(listed.status_code, 200)
        self.assertIn(self.product_a.id, [row["id"] for row in listed.data["results"]])
        self.assertEqual(self.client.patch(f"/api/v1/products/{self.product_a.id}/", {"brand": "Denied"}, format="json").status_code, 403)
        self.authenticate(self.editor)
        updated = self.client.patch(f"/api/v1/products/{self.product_a.id}/", {"brand": "Updated by staff"}, format="json")
        self.assertEqual(updated.status_code, 200, updated.data)

    def test_search_filters_sorting_and_validation(self):
        self.authenticate(self.owner_a)
        self.assertEqual(self.client.get("/api/v1/products/?search=English").data["count"], 1)
        self.assertEqual(self.client.get(f"/api/v1/products/?company_id={self.company_a.id}&ordering=sku").data["count"], 1)
        self.assertEqual(self.client.get(f"/api/v1/products/?company_id={self.company_b.id}").status_code, 400)
        invalid = self.client.post("/api/v1/products/", self.create_payload(sku="INVALID", ean="abc", variants=[]), format="json")
        self.assertEqual(invalid.status_code, 400)
