from django.contrib import admin
from django.db import transaction

from apps.users.models import User
from .forms import CustomerAdminForm
from .models import Customer, CustomerMembership


class CustomerMembershipInline(admin.TabularInline):
    model = CustomerMembership
    extra = 0
    autocomplete_fields = ("user", "role")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    form = CustomerAdminForm
    inlines = (CustomerMembershipInline,)
    list_display = ("email", "first_name", "last_name", "company", "has_login", "is_active")
    list_filter = ("is_active", "open_date")
    search_fields = ("email", "first_name", "last_name", "company")
    readonly_fields = ("user", "created_at", "updated_at")
    fieldsets = (
        ("Customer", {"fields": ("first_name", "last_name", "company", "phone", "email", "address", "open_date", "is_active")}),
        ("Login credentials", {"fields": ("password1", "password2", "user")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )

    @admin.display(boolean=True, description="Login")
    def has_login(self, customer):
        return customer.user_id is not None

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        password = form.cleaned_data.get("password1")
        if obj.user_id:
            user = obj.user
            if not user.is_superuser:
                user.email = obj.email
                user.first_name = obj.first_name
                user.last_name = obj.last_name
                user.is_active = obj.is_active
                update_fields = ["email", "first_name", "last_name", "is_active", "updated_at"]
                if password:
                    user.set_password(password)
                    update_fields.append("password")
                user.save(update_fields=update_fields)
        else:
            obj.user = User.objects.create_user(
                email=obj.email,
                password=password,
                first_name=obj.first_name,
                last_name=obj.last_name,
                is_active=obj.is_active,
            )
        super().save_model(request, obj, form, change)
        if obj.user_id and not obj.user.is_superuser:
            CustomerMembership.objects.update_or_create(
                customer=obj,
                user=obj.user,
                defaults={"is_owner": True, "role": None, "is_active": obj.is_active},
            )


@admin.register(CustomerMembership)
class CustomerMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "customer", "is_owner", "role", "is_active")
    list_filter = ("is_owner", "is_active", "customer")
    search_fields = ("user__email", "customer__email", "customer__company")
    autocomplete_fields = ("customer", "user", "role")
