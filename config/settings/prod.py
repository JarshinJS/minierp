from .base import *

DEBUG = False

# Enforce SECRET_KEY to be set in environment for production
SECRET_KEY = env("SECRET_KEY")


# Ensure allowed hosts is configured properly in production via env
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

# Production Security Settings
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=True)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=True)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=True)
SECURE_CONTENT_TYPE_NOSNIFF = env.bool("SECURE_CONTENT_TYPE_NOSNIFF", default=True)

# Production Database (requires environment setup)
DATABASES = {
    "default": env.db("DATABASE_URL")
}

# Static file storage with compression (optional, e.g. ManifestStaticFilesStorage)
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
