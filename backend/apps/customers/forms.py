from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.users.models import User
from .models import Customer


class CustomerAdminForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput,
        required=False,
        help_text="Required for new customers. Leave blank when editing to keep the current password.",
    )
    password2 = forms.CharField(
        label="Password confirmation",
        widget=forms.PasswordInput,
        required=False,
    )

    class Meta:
        model = Customer
        exclude = ("user", "roles", "deleted_at")

    def clean_email(self):
        email = User.objects.normalize_email(self.cleaned_data["email"])
        users = User.objects.filter(email__iexact=email)
        if self.instance.user_id:
            users = users.exclude(pk=self.instance.user_id)
        if users.exists():
            raise forms.ValidationError("A login account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if not self.instance.user_id and not password1:
            self.add_error("password1", "A password is required when provisioning the customer owner login.")
        if password1 != password2:
            self.add_error("password2", "The two password fields do not match.")
        if password1:
            user = self.instance.user if self.instance.user_id else User(
                email=cleaned.get("email", ""),
                first_name=cleaned.get("first_name", ""),
                last_name=cleaned.get("last_name", ""),
            )
            try:
                validate_password(password1, user=user)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned
