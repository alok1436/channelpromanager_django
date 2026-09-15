import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-development-only")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = [x.strip() for x in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if x.strip()]
INSTALLED_APPS = [
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    "rest_framework", "rest_framework_simplejwt.token_blacklist", "drf_spectacular", "django_filters", "corsheaders",
    "apps.core", "apps.users", "apps.modules", "apps.permissions", "apps.roles", "apps.customers", "apps.staff", "apps.companies", "apps.warehouses", "apps.platforms", "apps.channels", "apps.products", "apps.orders",
]
MIDDLEWARE = ["django.middleware.security.SecurityMiddleware", "corsheaders.middleware.CorsMiddleware", "django.contrib.sessions.middleware.SessionMiddleware", "django.middleware.common.CommonMiddleware", "django.middleware.csrf.CsrfViewMiddleware", "django.contrib.auth.middleware.AuthenticationMiddleware", "django.contrib.messages.middleware.MessageMiddleware", "django.middleware.clickjacking.XFrameOptionsMiddleware"]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True, "OPTIONS": {"context_processors": ["django.template.context_processors.request", "django.contrib.auth.context_processors.auth", "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": os.getenv("POSTGRES_DB", "app_db"), "USER": os.getenv("POSTGRES_USER", "app_user"), "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""), "HOST": os.getenv("POSTGRES_HOST", "db"), "PORT": os.getenv("POSTGRES_PORT", "5432")}}
AUTH_PASSWORD_VALIDATORS = [{"NAME": f"django.contrib.auth.password_validation.{name}"} for name in ("UserAttributeSimilarityValidator", "MinimumLengthValidator", "CommonPasswordValidator", "NumericPasswordValidator")]
AUTH_USER_MODEL = "users.User"
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"], "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"], "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend", "rest_framework.filters.SearchFilter", "rest_framework.filters.OrderingFilter"], "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination", "PAGE_SIZE": 20, "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema", "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler", "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"], "DEFAULT_THROTTLE_RATES": {"anon": "100/hour"}}
SIMPLE_JWT = {"ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("ACCESS_TOKEN_LIFETIME_MINUTES", "60"))), "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("REFRESH_TOKEN_LIFETIME_DAYS", "7"))), "ROTATE_REFRESH_TOKENS": True, "BLACKLIST_AFTER_ROTATION": True}
SPECTACULAR_SETTINGS = {"TITLE": "Channel Pro Manager API", "VERSION": "1.0.0", "SERVE_INCLUDE_SCHEMA": False, "SECURITY": [{"bearerAuth": []}], "COMPONENTS": {"securitySchemes": {"bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}}}, "ENUM_NAME_OVERRIDES": {"ProductStatusEnum": "apps.products.models.ProductStatus.choices", "ChannelStatusEnum": "apps.channels.models.ChannelStatus.choices"}}
CORS_ALLOWED_ORIGINS = [x for x in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if x]
CSRF_TRUSTED_ORIGINS = [x for x in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if x]
CELERY_BROKER_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CHANNEL_ENCRYPTION_KEY = os.getenv("CHANNEL_ENCRYPTION_KEY", "")
PRODUCT_SUPPORTED_LANGUAGES = tuple(code.strip() for code in os.getenv("PRODUCT_SUPPORTED_LANGUAGES", "en,de,fr,it,es,nl").split(",") if code.strip())
