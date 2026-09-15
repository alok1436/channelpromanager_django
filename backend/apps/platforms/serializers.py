from rest_framework import serializers

from .models import Platform


class PlatformSerializer(serializers.ModelSerializer):
    class Meta:
        model = Platform
        fields = (
            "id", "name", "code", "description", "logo_url", "is_active",
            "created_at", "updated_at",
        )
        read_only_fields = ("created_at", "updated_at")
        extra_kwargs = {"is_active": {"default": True}}
        validators = []

    def validate_code(self, value):
        code = value.strip().lower()
        duplicate = Platform.objects.filter(code__iexact=code)
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError("A platform with this code already exists.")
        return code

