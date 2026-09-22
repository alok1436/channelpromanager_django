from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.generics import GenericAPIView
from rest_framework.viewsets import ModelViewSet
from rest_framework.parsers import MultiPartParser
from rest_framework import serializers as drf_serializers
from django.db import transaction
from drf_spectacular.utils import OpenApiExample, extend_schema

from apps.channels.models import Channel, Marketplace
from apps.channels.selectors import get_customer_channels
from apps.channels.serializers import (
    AuthorizationCallbackSerializer,
    AmazonManualCredentialSerializer,
    ChannelCredentialStatusSerializer,
    WooProductImportUploadSerializer,
    WooProductImportStatusSerializer,
    ChannelCreateSerializer,
    ChannelCredentialUpdateSerializer,
    ChannelMarketplaceSerializer,
    ChannelReadSerializer,
    ChannelUpdateSerializer,
    CustomerChannelSettingsSerializer,
    MarketplaceReplaceSerializer,
    MarketplaceAdminSerializer,
    MarketplaceSerializer,
    customer_channel_settings_data,
)
from apps.channels.services.amazon_service import build_amazon_authorization_url, complete_amazon_authorization
from apps.channels.services.channel_service import disconnect_channel, replace_channel_marketplaces
from apps.channels.services.credential_service import credential_status, set_channel_credentials, set_manual_amazon_credentials
from apps.channels.services.ebay_service import build_ebay_authorization_url, complete_ebay_authorization
from apps.core.audit import record_audit
from apps.core.permissions import HasModulePermission, IsSuperAdmin
from apps.core.tenant_permissions import CustomerModulePermission
from apps.customers.services import get_current_customer
from apps.platforms.models import Platform


class ChannelViewSet(ModelViewSet):
    queryset = Channel.objects.none()
    permission_classes = (CustomerModulePermission,)
    permission_module = "channels"
    permission_map = {
        "credential_status": "channels.view",
        "credentials": "channels.credentials",
        "amazon_credentials": "channels.credentials",
        "marketplaces": "channels.view",
        "update_marketplaces": "channels.update",
        "authorize": "channels.authorize",
        "disconnect": "channels.delete",
        "sync_orders": "orders.create",
        "import_woo_products": "products.create",
        "woo_product_import_status": "products.view",
    }
    filterset_fields = ("company", "platform", "status", "is_active", "country_code")
    search_fields = ("name", "company__name", "vat")
    ordering_fields = ("name", "created_at", "updated_at", "last_sync_at")

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not self.request.user.is_authenticated:
            return Channel.objects.none()
        if self.request.user.is_superuser:
            return Channel.objects.select_related(
                "company", "platform", "created_by", "updated_by",
                "amazon_credentials", "ebay_credentials", "cdiscount_credentials",
                "woocommerce_credentials", "otto_credentials",
            ).prefetch_related("channel_marketplaces__marketplace")
        return get_customer_channels(get_current_customer(self.request.user))

    def get_serializer_class(self):
        if self.action == "create":
            return ChannelCreateSerializer
        if self.action in {"update", "partial_update"}:
            return ChannelUpdateSerializer
        return ChannelReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        channel = serializer.save()
        output = ChannelReadSerializer(channel, context=self.get_serializer_context())
        record_audit(request, "created", channel, new_values=output.data)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        channel = self.get_object()
        old = ChannelReadSerializer(channel, context=self.get_serializer_context()).data
        serializer = self.get_serializer(channel, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        channel = serializer.save()
        output = ChannelReadSerializer(channel, context=self.get_serializer_context())
        record_audit(request, "updated", channel, old_values=old, new_values=output.data)
        return Response(output.data)

    def destroy(self, request, *args, **kwargs):
        channel = self.get_object()
        disconnect_channel(channel, request.user)
        record_audit(request, "disconnected", channel, new_values={"status": channel.status, "is_active": channel.is_active})
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=("post",))
    def disconnect(self, request, pk=None):
        channel = disconnect_channel(self.get_object(), request.user)
        record_audit(request, "disconnected", channel, new_values={"status": channel.status, "is_active": channel.is_active})
        return Response(ChannelReadSerializer(channel, context=self.get_serializer_context()).data)

    @action(detail=True, methods=("get",), url_path="credentials/status")
    def credential_status(self, request, pk=None):
        return Response(credential_status(self.get_object()))

    @action(detail=True, methods=("patch",))
    def credentials(self, request, pk=None):
        channel = self.get_object()
        serializer = ChannelCredentialUpdateSerializer(data=request.data, context={"channel": channel})
        serializer.is_valid(raise_exception=True)
        set_channel_credentials(channel, serializer.validated_data, partial=True)
        record_audit(request, "credentials_updated", channel, new_values={"configured": True, "platform": channel.platform.code})
        return Response(credential_status(channel))

    @extend_schema(
        summary="Configure Amazon credentials manually",
        description=(
            "Stores seller credentials for this Amazon channel. Use POST or PUT for a complete configuration "
            "and PATCH to rotate individual values. Tokens are encrypted and never returned."
        ),
        request=AmazonManualCredentialSerializer,
        responses={200: ChannelCredentialStatusSerializer},
        examples=[
            OpenApiExample(
                "Amazon seller credentials",
                value={"seller_id": "A1EXAMPLESELLER", "refresh_token": "Atzr|..."},
                request_only=True,
            ),
            OpenApiExample(
                "Configured response",
                value={
                    "configured": True,
                    "platform": "amazon",
                    "credential_status": "configured",
                    "updated_at": "2026-09-17T15:42:20Z",
                },
                response_only=True,
                status_codes=("200",),
            ),
        ],
    )
    @action(detail=True, methods=("post", "put", "patch"), url_path="amazon-credentials")
    def amazon_credentials(self, request, pk=None):
        channel = self.get_object()
        partial = request.method == "PATCH"
        serializer = AmazonManualCredentialSerializer(
            data=request.data,
            partial=partial,
            context={"channel": channel, "partial": partial},
        )
        serializer.is_valid(raise_exception=True)
        set_manual_amazon_credentials(channel, serializer.validated_data, partial=partial)
        output = credential_status(channel)
        audit_output = {**output, "updated_at": output["updated_at"].isoformat() if output["updated_at"] else None}
        record_audit(request, "amazon_credentials_updated", channel, new_values=audit_output)
        return Response(output)

    @action(detail=True, methods=("get",))
    def marketplaces(self, request, pk=None):
        channel = self.get_object()
        return Response(ChannelMarketplaceSerializer(channel.channel_marketplaces.select_related("marketplace"), many=True).data)

    @marketplaces.mapping.put
    def update_marketplaces(self, request, pk=None):
        channel = self.get_object()
        serializer = MarketplaceReplaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mappings = replace_channel_marketplaces(channel, serializer.validated_data["marketplace_ids"])
        record_audit(request, "marketplaces_updated", channel, new_values={"marketplace_ids": serializer.validated_data["marketplace_ids"]})
        return Response(ChannelMarketplaceSerializer(mappings, many=True).data)

    @action(detail=True, methods=("post",))
    def authorize(self, request, pk=None):
        channel = self.get_object()
        builders = {"amazon": build_amazon_authorization_url, "ebay": build_ebay_authorization_url}
        builder = builders.get(channel.platform.code)
        if builder is None:
            return Response({"detail": "This platform uses direct credential configuration."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"platform": channel.platform.code, "authorization_url": builder(channel)})

    @action(detail=True, methods=("post",), url_path="sync-orders")
    def sync_orders(self, request, pk=None):
        from apps.orders.services import get_order_service

        channel = self.get_object()
        result = get_order_service(channel).download_orders()
        record_audit(request, "orders_synced", channel, new_values=result.as_dict())
        return Response(result.as_dict())

    @extend_schema(
        summary="Import WooCommerce products from CSV",
        request=WooProductImportUploadSerializer,
        responses={202: WooProductImportStatusSerializer},
    )
    @action(detail=True, methods=("post",), url_path="woo-product-import", parser_classes=(MultiPartParser,))
    def import_woo_products(self, request, pk=None):
        from apps.products.models import WooProductImport
        from apps.products.tasks import import_woo_products

        channel = self.get_object()
        if channel.platform.code != "woocommerce":
            raise drf_serializers.ValidationError({"channel": "Select a WooCommerce channel."})
        serializer = WooProductImportUploadSerializer(data=request.data, context={"channel": channel})
        serializer.is_valid(raise_exception=True)
        job = WooProductImport.objects.create(
            customer=channel.customer, channel=channel, warehouse=serializer.validated_data["warehouse"],
            uploaded_by=request.user, language_code=serializer.validated_data["language_code"],
            source_file=serializer.validated_data["file"],
        )
        transaction.on_commit(lambda: import_woo_products.delay(job.pk))
        record_audit(request, "woo_product_import_queued", channel, new_values={"import_id": job.pk})
        return Response(WooProductImportStatusSerializer(job).data, status=status.HTTP_202_ACCEPTED)

    @extend_schema(
        summary="Check WooCommerce product import",
        responses={200: WooProductImportStatusSerializer},
    )
    @action(detail=True, methods=("get",), url_path=r"woo-product-import/(?P<import_id>\d+)")
    def woo_product_import_status(self, request, pk=None, import_id=None):
        from django.shortcuts import get_object_or_404
        from apps.products.models import WooProductImport

        channel = self.get_object()
        job = get_object_or_404(WooProductImport, pk=import_id, channel=channel, customer=channel.customer)
        return Response(WooProductImportStatusSerializer(job).data)


class MarketplaceAdminViewSet(ModelViewSet):
    queryset = Marketplace.objects.select_related("platform").all()
    serializer_class = MarketplaceAdminSerializer
    permission_classes = (IsSuperAdmin,)
    filterset_fields = ("platform", "platform__code", "country_code", "is_active")
    search_fields = ("name", "code", "external_marketplace_id", "platform__name")
    ordering_fields = ("name", "code", "country_code", "created_at", "updated_at")


class CustomerChannelSettingsView(GenericAPIView):
    permission_classes = (HasModulePermission,)
    required_permission = "channels.credentials"
    serializer_class = CustomerChannelSettingsSerializer

    def get(self, request):
        return Response(customer_channel_settings_data(get_current_customer(request.user)))

    def patch(self, request):
        customer = get_current_customer(request.user)
        serializer = self.get_serializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.update_customer(customer)
        record_audit(request, "channel_settings_updated", customer, new_values={"providers": list(serializer.validated_data)})
        return Response(customer_channel_settings_data(customer))


class PlatformMarketplaceListView(GenericAPIView):
    permission_classes = (IsAuthenticated,)
    serializer_class = MarketplaceSerializer

    def get(self, request, platform_code):
        platform = Platform.objects.filter(code=platform_code.lower(), is_active=True).first()
        if platform is None:
            return Response({"detail": "Platform not found."}, status=status.HTTP_404_NOT_FOUND)
        marketplaces = Marketplace.objects.filter(platform=platform, is_active=True)
        return Response(MarketplaceSerializer(marketplaces, many=True).data)


class AmazonCallbackView(GenericAPIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    serializer_class = AuthorizationCallbackSerializer

    def get(self, request):
        serializer = AuthorizationCallbackSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data.get("spapi_oauth_code") or serializer.validated_data.get("code")
        seller_id = serializer.validated_data.get("selling_partner_id")
        if not code or not seller_id:
            return Response({"detail": "Amazon authorization code and seller ID are required."}, status=status.HTTP_400_BAD_REQUEST)
        channel = complete_amazon_authorization(raw_state=serializer.validated_data["state"], authorization_code=code, seller_id=seller_id)
        return Response({"success": True, "channel_id": channel.id, "platform": "amazon", "status": channel.status})


class EbayCallbackView(GenericAPIView):
    authentication_classes = ()
    permission_classes = (AllowAny,)
    serializer_class = AuthorizationCallbackSerializer

    def get(self, request):
        serializer = AuthorizationCallbackSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        code = serializer.validated_data.get("code")
        if not code:
            return Response({"detail": "eBay authorization code is required."}, status=status.HTTP_400_BAD_REQUEST)
        channel = complete_ebay_authorization(raw_state=serializer.validated_data["state"], authorization_code=code)
        return Response({"success": True, "channel_id": channel.id, "platform": "ebay", "status": channel.status})
