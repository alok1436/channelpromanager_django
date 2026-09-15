from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from apps.users.models import User
from apps.modules.models import Module
from apps.permissions.models import Permission
from apps.roles.models import Role, RolePermission
from apps.customers.models import Customer, CustomerMembership
from apps.orders.models import Order

class RBACAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_permissions", verbosity=0)
        cls.superuser = User.objects.create_superuser("root@example.com", "StrongPass123!")
        cls.user = User.objects.create_user("member@example.com", "StrongPass123!")
        cls.customer = Customer.objects.create(user=cls.user, first_name="John", last_name="Smith", email="john@example.com", company="ABC")
        cls.order_customer = Customer.objects.create(first_name="Buyer", last_name="One", email="buyer@example.com")
        cls.view_role = Role.objects.create(customer=cls.customer, name="Order Viewer", slug="order-viewer")
        RolePermission.objects.create(role=cls.view_role, permission=Permission.objects.get(codename="orders.view"))
        CustomerMembership.objects.create(customer=cls.customer, user=cls.user, role=cls.view_role, is_owner=False)
        cls.order = Order.objects.create(order_number="ORD-1", customer=cls.order_customer, total="10.00")

    def setUp(self): self.client = APIClient()
    def authenticate(self, user): self.client.force_authenticate(user)

    def test_jwt_login_and_me(self):
        response = self.client.post("/api/v1/auth/login/", {"email": "member@example.com", "password": "StrongPass123!"})
        self.assertEqual(response.status_code, 200); self.assertIn("access", response.data)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        me = self.client.get("/api/v1/auth/me/")
        self.assertEqual(me.status_code, 200); self.assertIn("orders.view", me.data["permissions"])

    def test_unauthenticated_is_rejected(self): self.assertEqual(self.client.get("/api/v1/orders/").status_code, 401)

    def test_view_only_order_permissions(self):
        self.authenticate(self.user)
        self.assertEqual(self.client.get("/api/v1/orders/").status_code, 200)
        payload = {"order_number": "ORD-2", "customer": self.order_customer.id, "total": "12.00", "currency": "USD"}
        self.assertEqual(self.client.post("/api/v1/orders/", payload).status_code, 403)
        self.assertEqual(self.client.patch(f"/api/v1/orders/{self.order.id}/", {"status": "completed"}).status_code, 403)
        self.assertEqual(self.client.delete(f"/api/v1/orders/{self.order.id}/").status_code, 403)

    def test_multiple_roles_merge_and_create_order(self):
        RolePermission.objects.create(role=self.view_role, permission=Permission.objects.get(codename="orders.create"))
        self.authenticate(self.user)
        matrix = self.client.get("/api/v1/auth/permissions/").data["permissions"]
        self.assertTrue(matrix["orders"]["view"]); self.assertTrue(matrix["orders"]["create"])
        response = self.client.post("/api/v1/orders/", {"order_number": "ORD-2", "customer": self.order_customer.id, "total": "12.00", "currency": "USD"})
        self.assertEqual(response.status_code, 201)

    def test_superadmin_bypass_and_management(self):
        self.authenticate(self.superuser)
        self.assertEqual(self.client.post("/api/v1/modules/", {"name": "Billing", "slug": "billing", "sort_order": 50}).status_code, 201)
        module = Module.objects.get(slug="billing")
        permission_response = self.client.post("/api/v1/permissions/", {"module": module.id, "name": "View Billing", "codename": "billing.view"})
        self.assertEqual(permission_response.status_code, 201, permission_response.data)
        self.assertTrue(Permission.objects.filter(codename="billing.view", is_active=True).exists(), Permission.objects.get(codename="billing.view").is_active)
        from apps.roles.serializers import RoleSerializer
        probe = RoleSerializer(data={"name": "Probe", "permissions": ["billing.view"]})
        self.assertTrue(probe.is_valid(), probe.errors)
        role = self.client.post("/api/v1/roles/", {"name": "Billing Viewer", "permissions": ["billing.view"]})
        self.assertEqual(role.status_code, 201, role.data)
        customer = self.client.post("/api/v1/customers/", {"first_name": "New", "last_name": "Customer", "email": "new@example.com", "password": "CustomerPass2026!"})
        self.assertEqual(customer.status_code, 201); self.assertTrue(CustomerMembership.objects.filter(customer_id=customer.data["id"], is_owner=True).exists())
        self.assertEqual(self.client.delete(f"/api/v1/orders/{self.order.id}/").status_code, 204)

    def test_non_superuser_cannot_manage_rbac(self):
        self.authenticate(self.user)
        self.assertEqual(self.client.get("/api/v1/roles/").status_code, 403)
        self.assertEqual(self.client.post("/api/v1/permissions/", {}).status_code, 403)

    def test_customer_crud_permission_mapping(self):
        role = Role.objects.create(customer=self.customer, name="Customer Admin", slug="customer-admin")
        permissions = Permission.objects.filter(codename__in=["customers.view", "customers.create", "customers.update", "customers.delete"])
        RolePermission.objects.bulk_create([RolePermission(role=role, permission=p) for p in permissions])
        membership = CustomerMembership.objects.get(user=self.user, customer=self.customer)
        membership.role = role
        membership.save(update_fields=("role", "updated_at"))
        self.authenticate(self.user)
        created = self.client.post("/api/v1/customers/", {"first_name": "Alice", "last_name": "Jones", "email": "alice@example.com", "password": "CustomerPass2026!"})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(self.client.patch(f"/api/v1/customers/{created.data['id']}/", {"company": "Acme"}).status_code, 200)
        self.assertEqual(self.client.get("/api/v1/customers/?search=alice&ordering=-created_at").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/v1/customers/{created.data['id']}/").status_code, 204)
        self.assertFalse(Customer.objects.get(pk=created.data["id"]).is_active)
        self.assertFalse(User.objects.get(email="alice@example.com").is_active)

    def test_customer_list_excludes_soft_deleted_customers(self):
        deleted_customer = Customer.objects.create(
            first_name="Deleted", last_name="Admin", email="deleted-admin@example.com"
        )
        deleted_customer.deleted_at = deleted_customer.created_at
        deleted_customer.is_active = False
        deleted_customer.save(update_fields=("deleted_at", "is_active", "updated_at"))

        self.authenticate(self.superuser)
        response = self.client.get("/api/v1/customers/")

        self.assertEqual(response.status_code, 200)
        rows = response.data.get("results", response.data)
        self.assertNotIn(deleted_customer.id, [row["id"] for row in rows])

    def test_customer_creation_provisions_login_and_password_is_write_only(self):
        self.authenticate(self.superuser)
        response = self.client.post("/api/v1/customers/", {"first_name": "Login", "last_name": "Customer", "email": "login-customer@example.com", "password": "CustomerPass2026!"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["has_login"])
        self.assertNotIn("password", response.data)
        self.client.force_authenticate(user=None)
        login = self.client.post("/api/v1/auth/login/", {"email": "login-customer@example.com", "password": "CustomerPass2026!"}, format="json")
        self.assertEqual(login.status_code, 200, login.data)
        self.assertIn("access", login.data)

    def test_customer_creation_requires_password(self):
        self.authenticate(self.superuser)
        response = self.client.post("/api/v1/customers/", {"first_name": "No", "last_name": "Password", "email": "no-password@example.com"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.data["errors"])

    def test_password_patch_provisions_login_for_legacy_customer(self):
        self.authenticate(self.superuser)
        response = self.client.patch(f"/api/v1/customers/{self.order_customer.id}/", {"password": "LegacyPass2026!"}, format="json")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["has_login"])
        self.client.force_authenticate(user=None)
        login = self.client.post("/api/v1/auth/login/", {"email": "buyer@example.com", "password": "LegacyPass2026!"}, format="json")
        self.assertEqual(login.status_code, 200, login.data)

    def test_superadmin_uses_django_flag_not_a_role(self):
        self.assertTrue(self.superuser.is_superuser)
        self.assertFalse(Role.objects.filter(slug="super-admin").exists())

    def test_customer_changes_cannot_deactivate_linked_superuser(self):
        protected_customer = Customer.objects.create(user=self.superuser, first_name="Protected", last_name="Admin", email="protected-admin@example.com")
        self.authenticate(self.superuser)
        response = self.client.patch(f"/api/v1/customers/{protected_customer.id}/", {"is_active": False}, format="json")
        self.assertEqual(response.status_code, 200)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)
        self.assertEqual(self.client.delete(f"/api/v1/customers/{protected_customer.id}/").status_code, 204)
        self.superuser.refresh_from_db()
        self.assertTrue(self.superuser.is_active)

    def test_seed_is_idempotent(self):
        before = (Module.objects.count(), Permission.objects.count()); call_command("seed_permissions", verbosity=0)
        self.assertEqual(before, (Module.objects.count(), Permission.objects.count()))
