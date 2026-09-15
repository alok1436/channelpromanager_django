from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from apps.users.models import User
from .admin import CustomerAdmin
from .forms import CustomerAdminForm
from .models import Customer


class CustomerAdminTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser("admin-form@example.com", "AdminPass2026!")
        self.request = RequestFactory().post("/admin/customers/customer/add/")
        self.request.user = self.admin_user
        self.model_admin = CustomerAdmin(Customer, AdminSite())

    def test_admin_requires_password_for_new_customer(self):
        form = CustomerAdminForm(data={"first_name": "No", "last_name": "Password", "email": "no-admin-password@example.com", "is_active": True})
        self.assertFalse(form.is_valid())
        self.assertIn("password1", form.errors)

    def test_admin_creates_customer_login_with_hashed_password(self):
        form = CustomerAdminForm(data={
            "first_name": "Admin", "last_name": "Customer",
            "email": "admin-created-customer@example.com", "is_active": True,
            "password1": "CustomerAdminPass2026!", "password2": "CustomerAdminPass2026!",
        })
        self.assertTrue(form.is_valid(), form.errors)
        customer = form.save(commit=False)
        self.model_admin.save_model(self.request, customer, form, change=False)
        customer.refresh_from_db()
        self.assertIsNotNone(customer.user_id)
        self.assertTrue(customer.user.check_password("CustomerAdminPass2026!"))
        self.assertNotEqual(customer.user.password, "CustomerAdminPass2026!")
