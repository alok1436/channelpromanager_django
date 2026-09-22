from django.conf import settings
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.customers.services import get_customer_membership, has_customer_permission
from apps.products.services.translation_service import normalize_language_code


def available_languages():
    regional = {
        "en": ("en-GB", "en-US"), "de": ("de-DE", "de-AT"),
        "fr": ("fr-FR",), "it": ("it-IT",),
        "es": ("es-ES",), "nl": ("nl-NL",),
    }
    base_codes = list(settings.PRODUCT_SUPPORTED_LANGUAGES)
    return base_codes + [code for base in base_codes for code in regional.get(base, ())]


def selected_languages(customer):
    return customer.product_languages or ["en"]


class ProductLanguageSettingsSerializer(serializers.Serializer):
    language_codes = serializers.ListField(child=serializers.CharField(max_length=10), min_length=1)

    def validate_language_codes(self, codes):
        normalized = [normalize_language_code(code) for code in codes]
        if len({code.lower() for code in normalized}) != len(normalized):
            raise serializers.ValidationError("Languages must be unique.")
        return normalized


class ProductLanguageSettingsResponseSerializer(ProductLanguageSettingsSerializer):
    available_languages = serializers.ListField(child=serializers.CharField(max_length=10), read_only=True)


class ProductLanguageSettingsView(APIView):
    permission_classes = (IsAuthenticated,)

    def _membership(self, request, permission):
        from rest_framework.exceptions import PermissionDenied

        membership = get_customer_membership(request.user)
        if membership is None or not has_customer_permission(request.user, membership.customer, permission):
            raise PermissionDenied("You do not have permission to manage product languages.")
        return membership

    @extend_schema(responses=ProductLanguageSettingsResponseSerializer)
    def get(self, request):
        customer = self._membership(request, "products.view").customer
        return Response({"language_codes": selected_languages(customer), "available_languages": available_languages()})

    @extend_schema(request=ProductLanguageSettingsSerializer, responses=ProductLanguageSettingsResponseSerializer)
    @transaction.atomic
    def put(self, request):
        customer = self._membership(request, "products.update").customer
        serializer = ProductLanguageSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        customer.product_languages = serializer.validated_data["language_codes"]
        customer.save(update_fields=("product_languages", "updated_at"))
        return Response({"language_codes": customer.product_languages, "available_languages": available_languages()})
