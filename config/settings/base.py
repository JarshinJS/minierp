import os
from pathlib import Path

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / ".env")


def _csv(value):
    return [item.strip() for item in value.split(",") if item.strip()]

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("SECRET_KEY must be set in the environment.")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = _csv(os.getenv("ALLOWED_HOSTS", ""))
CSRF_TRUSTED_ORIGINS = _csv(os.getenv("CSRF_TRUSTED_ORIGINS", ""))

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    
    # Third party apps
    "rest_framework",
    "django_filters",
    "django_htmx",
    
    # Local Core Layer
    "core",
    
    # Local Business Apps
    "apps.accounts.apps.AccountsConfig",
    "apps.products.apps.ProductsConfig",
    "apps.inventory.apps.InventoryConfig",
    "apps.sales.apps.SalesConfig",
    "apps.purchase.apps.PurchaseConfig",
    "apps.manufacturing.apps.ManufacturingConfig",
    "apps.procurement.apps.ProcurementConfig",
    "apps.delivery.apps.DeliveryConfig",
    "apps.reports.apps.ReportsConfig",
    "apps.audit_logs.apps.AuditLogsConfig",
    "apps.dashboard.apps.DashboardConfig",
    "apps.foreign_trade.apps.ForeignTradeConfig",
    "apps.blockchain.apps.BlockchainConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database
# Override in dev.py or prod.py as needed
DATABASES = {
    "default": {
        "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.getenv("DB_NAME", str(BASE_DIR / "db.sqlite3")),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", ""),
        "PORT": os.getenv("DB_PORT", ""),
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATICFILES_DIRS = [
    BASE_DIR / "static",
]
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django REST Framework Config
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 25,
}

# Celery Configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

# Authentication Customizations
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "accounts:login"

# Blockchain / Web3 Configuration
WEB3_PROVIDER_URL = os.getenv("WEB3_PROVIDER_URL", "")
BLOCKCHAIN_WALLET_ADDRESS = os.getenv("BLOCKCHAIN_WALLET_ADDRESS", "")
BLOCKCHAIN_NETWORK_NAME = os.getenv("BLOCKCHAIN_NETWORK_NAME", "polygon-amoy")
BLOCKCHAIN_MOCK_MODE = os.getenv("BLOCKCHAIN_MOCK_MODE", "True").lower() == "true"
