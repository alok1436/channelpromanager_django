from django.test import TestCase
from rest_framework.test import APIClient

from apps.customers.models import Customer
from apps.customers.models import CustomerMembership
from apps.users.models import User
from .models import Company


class CompanyAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user_a = User.objects.create_user("a@example.com", "StrongPass123!")
        cls.user_b = User.objects.create_user("b@example.com", "StrongPass123!")
        cls.user_without_customer = User.objects.create_user("none@example.com", "StrongPass123!")
        cls.admin = User.objects.create_superuser("admin@example.com", "StrongPass123!")
        cls.customer_a = Customer.objects.create(user=cls.user_a, first_name="A", last_name="Owner", email="a-customer@example.com")
        cls.customer_b = Customer.objects.create(user=cls.user_b, first_name="B", last_name="Owner", email="b-customer@example.com")
        CustomerMembership.objects.create(customer=cls.customer_a, user=cls.user_a, is_owner=True)
        CustomerMembership.objects.create(customer=cls.customer_b, user=cls.user_b, is_owner=True)
        cls.company_a = Company.objects.create(customer=cls.customer_a, name="Acme Limited")
        cls.company_b = Company.objects.create(customer=cls.customer_b, name="Beta Limited")

    def setUp(self):
        self.client = APIClient()

    def test_customer_lists_only_owned_companies(self):
        self.client.force_authenticate(self.user_a)
        response = self.client.get("/api/v1/companies/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([item["id"] for item in response.data["results"]], [self.company_a.id])

    def test_customer_can_create_update_and_soft_delete_owned_company(self):
        self.client.force_authenticate(self.user_a)
        created = self.client.post("/api/v1/companies/", {
            "name": "New Company Limited",
            "street_1": "1 Main Street", "postal_code": "10001",
            "city": "London", "country": "United Kingdom",
            "phone": "+44123456789", "email": "office@example.com", "note": "Primary company",
        }, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        company = Company.objects.get(pk=created.data["id"])
        self.assertEqual(company.customer, self.customer_a)
        updated = self.client.patch(f"/api/v1/companies/{company.id}/", {"fax": "+44111111111"}, format="json")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(self.client.delete(f"/api/v1/companies/{company.id}/").status_code, 204)
        company.refresh_from_db()
        self.assertFalse(company.is_active)
        self.assertIsNotNone(company.deleted_at)

    def test_customer_cannot_access_or_assign_another_customer(self):
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.get(f"/api/v1/companies/{self.company_b.id}/").status_code, 404)
        response = self.client.post("/api/v1/companies/", {
            "customer": self.customer_b.id, "name": "Wrong Owner"
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_user_without_customer_profile_is_forbidden(self):
        self.client.force_authenticate(self.user_without_customer)
        self.assertEqual(self.client.get("/api/v1/companies/").status_code, 403)

    def test_superadmin_can_manage_all_customer_companies(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/v1/companies/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        created = self.client.post("/api/v1/companies/", {
            "customer": self.customer_b.id, "name": "Admin Created"
        }, format="json")
        self.assertEqual(created.status_code, 201, created.data)

    def test_duplicate_active_name_is_rejected_per_customer(self):
        self.client.force_authenticate(self.user_a)
        response = self.client.post("/api/v1/companies/", {
            "name": "acme limited"
        }, format="json")
        self.assertEqual(response.status_code, 400)
