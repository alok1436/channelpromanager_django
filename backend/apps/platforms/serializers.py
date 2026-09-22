from rest_framework import serializers

from .models import Platform


class PlatformSerializer(serializers.ModelSerializer):
    logo_url = serializers.SerializerMethodField()

    class Meta:
        model = Platform
        fields = (
            "id", "name", "code", "description", "logo", "logo_url", "is_active",
            "created_at", "updated_at",
        )
        read_only_fields = ("logo_url", "created_at", "updated_at")
        extra_kwargs = {"is_active": {"default": True}}
        validators = []

    def get_logo_url(self, platform):
        if not platform.logo:
            return platform.logo_url or ""
        request = self.context.get("request")
        return request.build_absolute_uri(platform.logo.url) if request else platform.logo.url

    def validate_logo(self, value):
        if value.size > 2 * 1024 * 1024:
            raise serializers.ValidationError("Logo must be 2 MB or smaller.")
        if getattr(value, "content_type", None) not in {"image/jpeg", "image/png", "image/webp"}:
            raise serializers.ValidationError("Logo must be a JPEG, PNG, or WebP image.")
        if value.image.width != 200 or value.image.height != 200:
            raise serializers.ValidationError("Logo must be exactly 200 × 200 pixels.")
        return value

    def validate_code(self, value):
        code = value.strip().lower()
        duplicate = Platform.objects.filter(code__iexact=code)
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError("A platform with this code already exists.")
        return code
