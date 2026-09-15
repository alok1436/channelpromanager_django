from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.customers.models import Customer, CustomerMembership
from apps.orders.models import Order
from apps.permissions.models import Permission
from apps.roles.models import Role, RolePermission
from apps.users.models import User


class MultiTenantSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_permissions", verbosity=0)
        cls.owner_a = User.objects.create_user("owner-a@example.com", "OwnerPass2026!")
        cls.owner_b = User.objects.create_user("owner-b@example.com", "OwnerPass2026!")
        cls.staff_a = User.objects.create_user("staff-a@example.com", "StaffPass2026!")
        cls.customer_a = Customer.objects.create(user=cls.owner_a, first_name="Owner", last_name="A", email="tenant-a@example.com", company="Tenant A")
        cls.customer_b = Customer.objects.create(user=cls.owner_b, first_name="Owner", last_name="B", email="tenant-b@example.com", company="Tenant B")
        CustomerMembership.objects.create(customer=cls.customer_a, user=cls.owner_a, is_owner=True)
        CustomerMembership.objects.create(customer=cls.customer_b, user=cls.owner_b, is_owner=True)
        cls.role_a = Role.objects.create(customer=cls.customer_a, name="Order Viewer", slug="order-viewer")
        RolePermission.objects.create(role=cls.role_a, permission=Permission.objects.get(codename="orders.view"))
        cls.staff_membership = CustomerMembership.objects.create(customer=cls.customer_a, user=cls.staff_a, role=cls.role_a)
        cls.order_a1 = Order.objects.create(customer=cls.customer_a, order_number="A-1", total="10.00")
        cls.order_a2 = Order.objects.create(customer=cls.customer_a, order_number="A-2", total="20.00")
        cls.order_b = Order.objects.create(customer=cls.customer_b, order_number="B-1", total="30.00")

    def setUp(self):
        self.client = APIClient()

    def test_owner_has_full_tenant_access_but_not_other_tenant(self):
        self.client.force_authenticate(self.owner_a)
        orders = self.client.get("/api/v1/orders/")
        self.assertEqual(orders.status_code, 200)
        self.assertEqual({item["order_number"] for item in orders.data["results"]}, {"A-1", "A-2"})
        created = self.client.post("/api/v1/orders/", {"order_number": "A-3", "total": "40.00", "currency": "USD"}, format="json")
        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(Order.objects.get(order_number="A-3").customer, self.customer_a)
        self.assertEqual(self.client.get(f"/api/v1/orders/{self.order_b.id}/").status_code, 404)

    def test_staff_views_all_tenant_orders_not_only_created_records(self):
        self.client.force_authenticate(self.staff_a)
        response = self.client.get("/api/v1/orders/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual({item["order_number"] for item in response.data["results"]}, {"A-1", "A-2"})
        self.assertEqual(self.client.get(f"/api/v1/orders/{self.order_b.id}/").status_code, 404)

    def test_staff_action_permissions_and_cross_tenant_update(self):
        self.client.force_authenticate(self.staff_a)
        self.assertEqual(self.client.post("/api/v1/orders/", {"order_number": "DENIED", "total": "1.00"}, format="json").status_code, 403)
        self.assertEqual(self.client.patch(f"/api/v1/orders/{self.order_a1.id}/", {"status": "completed"}, format="json").status_code, 403)
        RolePermission.objects.create(role=self.role_a, permission=Permission.objects.get(codename="orders.update"))
        self.assertEqual(self.client.patch(f"/api/v1/orders/{self.order_a1.id}/", {"status": "completed"}, format="json").status_code, 200)
        self.assertEqual(self.client.patch(f"/api/v1/orders/{self.order_b.id}/", {"status": "completed"}, format="json").status_code, 404)

    def test_owner_manages_only_own_roles_and_rejects_foreign_role_for_staff(self):
        foreign_role = Role.objects.create(customer=self.customer_b, name="Foreign", slug="foreign")
        self.client.force_authenticate(self.owner_a)
        roles = self.client.get("/api/v1/roles/")
        self.assertEqual(roles.status_code, 200)
        self.assertNotIn(foreign_role.id, [item["id"] for item in roles.data["results"]])
        self.assertEqual(self.client.get(f"/api/v1/roles/{foreign_role.id}/").status_code, 404)
        response = self.client.post("/api/v1/staff/", {"first_name": "New", "last_name": "Staff", "email": "new-staff@example.com", "password": "NewStaffPass2026!", "role_id": foreign_role.id}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_staff_cannot_change_own_role(self):
        RolePermission.objects.create(role=self.role_a, permission=Permission.objects.get(codename="staff.update"))
        self.client.force_authenticate(self.staff_a)
        response = self.client.patch(f"/api/v1/staff/{self.staff_membership.id}/", {"role_id": self.role_a.id}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_owner_can_create_staff_for_current_customer(self):
        self.client.force_authenticate(self.owner_a)
        response = self.client.post("/api/v1/staff/", {"first_name": "New", "last_name": "Staff", "email": "staff-new@example.com", "phone": "123", "password": "NewStaffPass2026!", "role_id": self.role_a.id}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        membership = CustomerMembership.objects.get(pk=response.data["id"])
        self.assertEqual(membership.customer, self.customer_a)
        self.assertFalse(membership.is_owner)
