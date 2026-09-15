from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.companies.models import Company
from apps.customers.models import Customer, CustomerMembership
from apps.permissions.models import Permission
from apps.roles.models import Role, RolePermission
from apps.users.models import User
from .models import Warehouse


class WarehouseAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_permissions", verbosity=0)
        cls.owner_a = User.objects.create_user("warehouse-a@example.com", "StrongPass123!")
        cls.owner_b = User.objects.create_user("warehouse-b@example.com", "StrongPass123!")
        cls.staff = User.objects.create_user("warehouse-staff@example.com", "StrongPass123!")
        cls.admin = User.objects.create_superuser("warehouse-admin@example.com", "StrongPass123!")
        cls.customer_a = Customer.objects.create(
            user=cls.owner_a, first_name="A", last_name="Owner", email="warehouse-a-customer@example.com"
        )
        cls.customer_b = Customer.objects.create(
            user=cls.owner_b, first_name="B", last_name="Owner", email="warehouse-b-customer@example.com"
        )
        CustomerMembership.objects.create(customer=cls.customer_a, user=cls.owner_a, is_owner=True)
        CustomerMembership.objects.create(customer=cls.customer_b, user=cls.owner_b, is_owner=True)
        cls.company_a = Company.objects.create(customer=cls.customer_a, name="Company A")
        cls.company_b = Company.objects.create(customer=cls.customer_b, name="Company B")
        cls.warehouse_a = Warehouse.objects.create(customer=cls.customer_a, company=cls.company_a, name="A Main")
        cls.warehouse_b = Warehouse.objects.create(customer=cls.customer_b, company=cls.company_b, name="B Main")

    def setUp(self):
        self.client = APIClient()

    def test_owner_lists_only_warehouses_for_owned_customer(self):
        self.client.force_authenticate(self.owner_a)
        response = self.client.get("/api/v1/warehouses/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row["id"] for row in response.data["results"]], [self.warehouse_a.id])

    def test_owner_can_create_update_and_delete_warehouse(self):
        self.client.force_authenticate(self.owner_a)
        created = self.client.post("/api/v1/warehouses/", {
            "company": self.company_a.id, "name": "Returns", "street1": "1 Main Street",
            "street2": "Unit 2", "plz": "10001", "city": "London", "province": "London",
            "country": "United Kingdom", "phone": "+44123456789", "fax": "+44111111111",
            "email": "returns@example.com", "notes": "Returns warehouse",
        }, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        warehouse_id = created.data["id"]
        updated = self.client.patch(f"/api/v1/warehouses/{warehouse_id}/", {"city": "Manchester"}, format="json")
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data["city"], "Manchester")
        self.assertEqual(self.client.delete(f"/api/v1/warehouses/{warehouse_id}/").status_code, 204)
        self.assertFalse(Warehouse.objects.filter(pk=warehouse_id).exists())

    def test_owner_cannot_access_or_assign_another_customer(self):
        self.client.force_authenticate(self.owner_a)
        self.assertEqual(self.client.get(f"/api/v1/warehouses/{self.warehouse_b.id}/").status_code, 404)
        response = self.client.post("/api/v1/warehouses/", {
            "customer_id": self.customer_b.id, "company": self.company_b.id, "name": "Wrong tenant"
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_owner_cannot_assign_another_customers_company(self):
        self.client.force_authenticate(self.owner_a)
        response = self.client.post("/api/v1/warehouses/", {
            "company": self.company_b.id, "name": "Wrong company"
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_staff_requires_warehouse_permissions(self):
        role = Role.objects.create(customer=self.customer_a, name="Warehouse Viewer", slug="warehouse-viewer")
        RolePermission.objects.create(role=role, permission=Permission.objects.get(codename="warehouses.view"))
        CustomerMembership.objects.create(customer=self.customer_a, user=self.staff, role=role)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get("/api/v1/warehouses/").status_code, 200)
        self.assertEqual(self.client.post("/api/v1/warehouses/", {
            "company": self.company_a.id, "name": "Forbidden create"
        }, format="json").status_code, 403)

    def test_superadmin_can_manage_all_warehouses(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/v1/warehouses/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
