from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.companies.models import Company
from apps.core.audit import record_audit
from apps.core.tenant_permissions import CustomerModulePermission
from apps.customers.services import get_current_customer
from apps.products.models import Product, ProductImage, ProductTranslation, ProductVariant, ProductStatus
from apps.products.selectors import get_customer_product, product_detail_for_customer, product_list_for_customer
from apps.products.serializers import (
    BulkArchiveSerializer, BulkStatusSerializer, ImageReorderSerializer, ImageUpdateSerializer,
    ProductCreateSerializer, ProductDetailSerializer, ProductImageSerializer, ProductListSerializer,
    ProductTranslationSerializer, ProductUpdateSerializer, ProductVariantSerializer,
)
from apps.products.services.image_service import create_image, delete_image, reorder_images, update_image
from apps.products.services.product_service import archive_product, bulk_status, duplicate_product, restore_product
from apps.products.services.translation_service import create_translation, update_translation
from apps.products.services.variant_service import create_variant, update_variant


class ProductViewSet(ModelViewSet):
    queryset = Product.objects.none()
    permission_classes = (CustomerModulePermission,)
    permission_module = "products"
    parser_classes = (JSONParser, MultiPartParser, FormParser)
    permission_map = {
        "archive": "products.delete", "restore": "products.update", "duplicate": "products.create",
        "translations": "products.view", "add_translation": "products.update", "translation_detail": "products.update",
        "images": "products.view", "add_image": "products.update", "image_detail": "products.update",
        "reorder_images": "products.update", "variants": "products.view", "add_variant": "products.update",
        "variant_detail": "products.update", "bulk_status_action": "products.update", "bulk_archive": "products.delete",
    }
    filterset_fields = ("status", "condition", "brand", "product_type", "is_active")
    search_fields = ("sku", "ean", "upc", "gtin", "mpn", "brand", "manufacturer", "translations__name")
    ordering_fields = ("sku", "created_at", "updated_at", "standard_sale_price", "brand")
    ordering = ("-updated_at",)

    def get_permissions(self):
        if getattr(self, "action", None) in {"translation_detail", "image_detail", "variant_detail"} and self.request.method == "DELETE":
            self.permission_map = {**self.permission_map, self.action: "products.delete"}
        return super().get_permissions()

    def get_customer(self):
        return get_current_customer(self.request.user)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated or self.request.user.is_superuser:
            return Product.objects.none()
        customer = self.get_customer()
        queryset = product_list_for_customer(customer) if getattr(self, "action", "list") == "list" else product_detail_for_customer(customer)
        company_id = self.request.query_params.get("company_id")
        if company_id:
            if not company_id.isdigit() or not Company.objects.filter(customer=customer, pk=company_id).exists():
                raise serializers.ValidationError({"company_id": "Select a company belonging to your customer."})
            queryset = queryset.filter(company_id=company_id)
        return queryset

    def get_serializer_class(self):
        if self.action == "list":
            return ProductListSerializer
        if self.action == "create":
            return ProductCreateSerializer
        if self.action in {"update", "partial_update"}:
            return ProductUpdateSerializer
        return ProductDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["language"] = self.request.query_params.get("language", "")
        return context

    def _fresh(self, product_id):
        return get_customer_product(customer=self.get_customer(), product_id=product_id)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        product = self._fresh(product.id)
        output = ProductDetailSerializer(product, context=self.get_serializer_context())
        record_audit(request, "created", product, new_values={"sku": product.sku})
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        product = self.get_object()
        old = {"sku": product.sku, "status": product.status, "is_active": product.is_active}
        serializer = self.get_serializer(product, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        product = serializer.save()
        output = ProductDetailSerializer(self._fresh(product.id), context=self.get_serializer_context())
        record_audit(request, "updated", product, old_values=old, new_values={"sku": product.sku, "status": product.status, "is_active": product.is_active})
        return Response(output.data)

    def destroy(self, request, *args, **kwargs):
        product = archive_product(self.get_object(), request.user)
        record_audit(request, "archived", product, new_values={"status": product.status, "is_active": False})
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=("post",))
    def archive(self, request, pk=None):
        product = archive_product(self.get_object(), request.user)
        record_audit(request, "archived", product, new_values={"status": product.status, "is_active": False})
        return Response(ProductDetailSerializer(self._fresh(product.id), context=self.get_serializer_context()).data)

    @action(detail=True, methods=("post",))
    def restore(self, request, pk=None):
        product = restore_product(self.get_object(), request.user)
        record_audit(request, "restored", product, new_values={"status": product.status, "is_active": True})
        return Response(ProductDetailSerializer(self._fresh(product.id), context=self.get_serializer_context()).data)

    @action(detail=True, methods=("post",))
    def duplicate(self, request, pk=None):
        product = duplicate_product(self.get_object(), request.user)
        record_audit(request, "duplicated", product, new_values={"sku": product.sku})
        return Response(ProductDetailSerializer(self._fresh(product.id), context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=("get",))
    def translations(self, request, pk=None):
        return Response(ProductTranslationSerializer(self.get_object().translations.all(), many=True).data)

    @translations.mapping.post
    def add_translation(self, request, pk=None):
        product = self.get_object()
        serializer = ProductTranslationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        translation = create_translation(product, serializer.validated_data)
        record_audit(request, "translation_created", product, new_values={"language_code": translation.language_code})
        return Response(ProductTranslationSerializer(translation).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=("patch", "delete"), url_path=r"translations/(?P<translation_id>\d+)")
    def translation_detail(self, request, pk=None, translation_id=None):
        product = self.get_object()
        translation = get_object_or_404(ProductTranslation, product=product, customer=product.customer, pk=translation_id)
        if request.method == "DELETE":
            translation.delete()
            record_audit(request, "translation_deleted", product, old_values={"language_code": translation.language_code})
            return Response(status=status.HTTP_204_NO_CONTENT)
        serializer = ProductTranslationSerializer(translation, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        translation = update_translation(translation, serializer.validated_data)
        record_audit(request, "translation_updated", product, new_values={"language_code": translation.language_code})
        return Response(ProductTranslationSerializer(translation).data)

    @action(detail=True, methods=("get",))
    def images(self, request, pk=None):
        return Response(ProductImageSerializer(self.get_object().images.all(), many=True, context=self.get_serializer_context()).data)

    @images.mapping.post
    def add_image(self, request, pk=None):
        product = self.get_object()
        serializer = ProductImageSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        image = create_image(product, serializer.validated_data)
        record_audit(request, "image_created", product, new_values={"image_id": image.id})
        return Response(ProductImageSerializer(image, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=("patch", "delete"), url_path=r"images/(?P<image_id>\d+)")
    def image_detail(self, request, pk=None, image_id=None):
        product = self.get_object()
        image = get_object_or_404(ProductImage, product=product, customer=product.customer, pk=image_id)
        if request.method == "DELETE":
            deleted_id = image.id
            delete_image(image)
            record_audit(request, "image_deleted", product, old_values={"image_id": deleted_id})
            return Response(status=status.HTTP_204_NO_CONTENT)
        serializer = ImageUpdateSerializer(image, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        image = update_image(image, serializer.validated_data)
        return Response(ProductImageSerializer(image, context=self.get_serializer_context()).data)

    @action(detail=True, methods=("put",), url_path="images/reorder")
    def reorder_images(self, request, pk=None):
        product = self.get_object()
        serializer = ImageReorderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        images = reorder_images(product, serializer.validated_data["image_ids"])
        return Response(ProductImageSerializer(images, many=True, context=self.get_serializer_context()).data)

    @action(detail=True, methods=("get",))
    def variants(self, request, pk=None):
        return Response(ProductVariantSerializer(self.get_object().variants.all(), many=True).data)

    @variants.mapping.post
    def add_variant(self, request, pk=None):
        product = self.get_object()
        serializer = ProductVariantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        variant = create_variant(product, serializer.validated_data)
        record_audit(request, "variant_created", product, new_values={"variant_id": variant.id, "sku": variant.sku})
        return Response(ProductVariantSerializer(variant).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=("patch", "delete"), url_path=r"variants/(?P<variant_id>\d+)")
    def variant_detail(self, request, pk=None, variant_id=None):
        product = self.get_object()
        variant = get_object_or_404(ProductVariant, product=product, customer=product.customer, pk=variant_id)
        if request.method == "DELETE":
            variant.delete()
            record_audit(request, "variant_deleted", product, old_values={"variant_id": variant_id})
            return Response(status=status.HTTP_204_NO_CONTENT)
        serializer = ProductVariantSerializer(variant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        variant = update_variant(variant, serializer.validated_data)
        return Response(ProductVariantSerializer(variant).data)

    @action(detail=False, methods=("post",), url_path="bulk/status")
    def bulk_status_action(self, request):
        serializer = BulkStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        count = bulk_status(self.get_customer(), serializer.validated_data["product_ids"], serializer.validated_data["status"], request.user)
        return Response({"updated": count})

    @action(detail=False, methods=("post",), url_path="bulk/archive")
    def bulk_archive(self, request):
        serializer = BulkArchiveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        count = bulk_status(self.get_customer(), serializer.validated_data["product_ids"], ProductStatus.ARCHIVED, request.user)
        return Response({"updated": count})
