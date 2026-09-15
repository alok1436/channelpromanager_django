from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from apps.modules.views import ModuleViewSet
from apps.permissions.views import PermissionViewSet
from apps.roles.views import RoleViewSet
from apps.customers.views import CustomerViewSet
from apps.orders.views import OrderViewSet
from apps.companies.views import CompanyViewSet
from apps.warehouses.views import WarehouseViewSet
from apps.platforms.views import PlatformViewSet
from apps.channels.views import AmazonCallbackView, ChannelViewSet, CustomerChannelSettingsView, EbayCallbackView, MarketplaceAdminViewSet, PlatformMarketplaceListView
from apps.staff.views import StaffViewSet
from apps.users.views import MeView, CurrentPermissionsView, LogoutView
from apps.products.views import ProductViewSet
router = DefaultRouter()
router.register("modules", ModuleViewSet); router.register("permissions", PermissionViewSet); router.register("roles", RoleViewSet); router.register("customers", CustomerViewSet); router.register("staff", StaffViewSet, basename="staff"); router.register("companies", CompanyViewSet, basename="company"); router.register("warehouses", WarehouseViewSet, basename="warehouse"); router.register("platforms", PlatformViewSet, basename="platform"); router.register("channels", ChannelViewSet, basename="channel"); router.register("marketplaces", MarketplaceAdminViewSet, basename="marketplace"); router.register("products", ProductViewSet, basename="product"); router.register("orders", OrderViewSet)
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"), path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/v1/auth/login/", TokenObtainPairView.as_view(), name="login"), path("api/v1/auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"), path("api/v1/auth/logout/", LogoutView.as_view(), name="logout"), path("api/v1/auth/me/", MeView.as_view(), name="me"), path("api/v1/auth/permissions/", CurrentPermissionsView.as_view(), name="current-permissions"),
    path("api/v1/platforms/<str:platform_code>/marketplaces/", PlatformMarketplaceListView.as_view(), name="platform-marketplaces"),
    path("api/v1/channel-settings/", CustomerChannelSettingsView.as_view(), name="customer-channel-settings"),
    path("api/v1/channels/amazon/callback/", AmazonCallbackView.as_view(), name="amazon-channel-callback"),
    path("api/v1/channels/ebay/callback/", EbayCallbackView.as_view(), name="ebay-channel-callback"),
    path("api/v1/", include(router.urls)),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
