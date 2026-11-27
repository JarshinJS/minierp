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
    "drf_spectacular",
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
    "config.health.HealthCheckMiddleware",  # must stay first
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "core.middleware.AccountStatusMiddleware",  # blocks unapproved/suspended accounts
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
MEDIA_ROOT = BASE_DIR / "media"  # local-disk fallback; never served over HTTP

# --- Document storage ------------------------------------------------------------
# Trade documents go to PRIVATE object storage when STORAGE_BUCKET is set: Supabase
# Storage through its S3-compatible API (or any S3-compatible store). Without it,
# files are kept on local disk (development only). Either way there is no public
# URL: downloads go through the authenticated, signed
# /api/trade/documents/<id>/download/ endpoint, and the storage keys/credentials
# never reach the browser. The web service and the Celery worker must use the same
# bucket (the worker hashes files for blockchain anchoring).
STORAGE_BUCKET = os.getenv("STORAGE_BUCKET", "")
if STORAGE_BUCKET:
    _DEFAULT_STORAGE = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": STORAGE_BUCKET,
            # Supabase: https://<project-ref>.storage.supabase.co/storage/v1/s3
            "endpoint_url": os.getenv("STORAGE_ENDPOINT_URL") or None,
            "region_name": os.getenv("STORAGE_REGION") or None,
            "access_key": os.getenv("STORAGE_ACCESS_KEY_ID", ""),
            "secret_key": os.getenv("STORAGE_SECRET_ACCESS_KEY", ""),
            "location": os.getenv("STORAGE_PREFIX", ""),
            "default_acl": None,        # no public-read ACLs: the bucket stays private
            "querystring_auth": True,   # any storage URL ever generated is signed...
            "querystring_expire": 60,   # ...and short-lived (the app doesn't hand them out)
            "file_overwrite": False,    # never replace an existing object
            "addressing_style": "path",
            "signature_version": "s3v4",
        },
    }
else:
    _DEFAULT_STORAGE = {"BACKEND": "django.core.files.storage.FileSystemStorage"}
STORAGES = {
    "default": _DEFAULT_STORAGE,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
# Lifetime (seconds) of the signed download links in API responses.
DOCUMENT_DOWNLOAD_URL_TTL = int(os.getenv("DOCUMENT_DOWNLOAD_URL_TTL", "300"))
# Reject oversized request bodies early (uploads are capped at 10 MB by the validator).
DATA_UPLOAD_MAX_MEMORY_SIZE = 2_621_440
FILE_UPLOAD_MAX_MEMORY_SIZE = 2_621_440

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
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "core.api.exception_handler",
    # Only views that opt in (auth endpoints) are throttled.
    "DEFAULT_THROTTLE_RATES": {
        "auth": os.getenv("AUTH_THROTTLE_RATE", "10/min"),                    # per client IP
        "auth_account": os.getenv("AUTH_ACCOUNT_THROTTLE_RATE", "30/hour"),  # per login e-mail
    },
    # Reverse proxies in front of Django, used to find the client IP for throttling.
    # Render = 1; Vercel rewrite -> Render = 2.
    "NUM_PROXIES": int(os.getenv("NUM_PROXIES", "0")) or None,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "MiniERP API",
    "DESCRIPTION": (
        "Session-cookie auth: GET /api/auth/csrf/ first, then send the csrftoken "
        "cookie value as X-CSRFToken on unsafe requests."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAuthenticated"],
    "SCHEMA_PATH_PREFIX": r"/api/",
    "COMPONENT_SPLIT_REQUEST": True,  # separate request/response types for TS codegen
    "PREPROCESSING_HOOKS": ["core.api.api_paths_only"],
    "ENUM_NAME_OVERRIDES": {
        "TradeDocumentTypeEnum": "apps.foreign_trade.models.DocumentType",
        "ProcurementDocumentTypeEnum": "apps.procurement.models.ProcurementDocumentType",
    },
}

# Celery Configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
# Run tasks inline in the web process instead of on a worker. Useful for small
# deployments without Redis + a worker service; leave False when a worker runs.
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_TASK_ALWAYS_EAGER", "False").lower() == "true"
CELERY_TASK_EAGER_PROPAGATES = CELERY_TASK_ALWAYS_EAGER

# Voice assistant LLM (Ollama). Point at a reachable Ollama server in production.
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

# Email (used for signup OTPs and notifications)
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@localhost")

# Authentication Customizations
AUTH_USER_MODEL = "accounts.User"
# Login/signup pages live in the Next.js frontend, on the same domain.
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/login/"

# Public URL of the Next.js frontend (no trailing slash). Used to send people who
# hit the backend directly to pages that now live in the frontend. Optional.
FRONTEND_URL = os.getenv("FRONTEND_URL", "").rstrip("/")

# Blockchain / Web3 Configuration
WEB3_PROVIDER_URL = os.getenv("WEB3_PROVIDER_URL", "")
BLOCKCHAIN_WALLET_ADDRESS = os.getenv("BLOCKCHAIN_WALLET_ADDRESS", "")
BLOCKCHAIN_NETWORK_NAME = os.getenv("BLOCKCHAIN_NETWORK_NAME", "polygon-amoy")
BLOCKCHAIN_MOCK_MODE = os.getenv("BLOCKCHAIN_MOCK_MODE", "True").lower() == "true"
# The wallet private key is read only from the BLOCKCHAIN_WALLET_PRIVATE_KEY env var
# at signing time; it is deliberately not a Django setting.
# Gas: estimate_gas() x multiplier, refused above BLOCKCHAIN_MAX_GAS.
BLOCKCHAIN_GAS_LIMIT_MULTIPLIER = float(os.getenv("BLOCKCHAIN_GAS_LIMIT_MULTIPLIER", "1.2"))
BLOCKCHAIN_MAX_GAS = int(os.getenv("BLOCKCHAIN_MAX_GAS", "100000"))
# Fees (EIP-1559, in gwei). Polygon rejects priority fees below ~25 gwei. A submission
# whose max fee would exceed the cap is refused (and retried later), not overpaid.
BLOCKCHAIN_MIN_PRIORITY_FEE_GWEI = float(os.getenv("BLOCKCHAIN_MIN_PRIORITY_FEE_GWEI", "30"))
BLOCKCHAIN_MAX_FEE_PER_GAS_GWEI = float(os.getenv("BLOCKCHAIN_MAX_FEE_PER_GAS_GWEI", "500"))
# Seconds a worker waits for a receipt before giving up and retrying later.
BLOCKCHAIN_RECEIPT_TIMEOUT = int(os.getenv("BLOCKCHAIN_RECEIPT_TIMEOUT", "120"))
