# -----------------------------------------------------------------------------------
# Docker settings for the surveyor-modern RapidPro stack.
#
# Derived from RapidPro's own temba/settings.py.dev, but wired to the docker compose
# service names (postgres/redis/seaweedfs/mailroom) and environment variables.
# -----------------------------------------------------------------------------------

import warnings
import os
from urllib.parse import urlparse

import dj_database_url
from .settings_common import *  # noqa

# hardened defaults: debug off unless explicitly enabled, secret/hosts from environment
DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() in ("1", "true", "yes")
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "unsafe-dev-secret-change-me")
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]

# Behind a TLS-terminating proxy (nginx / ngrok). Without this Django treats the request as
# HTTP, so the HTTPS Origin header fails the CSRF check.
_proxy_ssl_header = os.environ.get("DJANGO_SECURE_PROXY_SSL_HEADER", "HTTP_X_FORWARDED_PROTO,https")
SECURE_PROXY_SSL_HEADER = tuple(p.strip() for p in _proxy_ssl_header.split(","))
USE_X_FORWARDED_HOST = True

# Origins permitted to POST (CSRF). Supports Django's "*" wildcard.
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "DJANGO_CSRF_TRUSTED_ORIGINS", "https://*.ngrok-free.app,https://app.ubuviz.com"
    ).split(",")
    if o.strip()
]

# Public hostname used for outbound links (media/survey) and the Django HOSTNAME.
# Empty keeps settings_common defaults (HOSTNAME=localhost, BRAND domain app.rapidpro.io).
PUBLIC_DOMAIN = os.environ.get("PUBLIC_DOMAIN", "").strip()
if PUBLIC_DOMAIN:
    HOSTNAME = PUBLIC_DOMAIN
    BRAND = {**BRAND, "domain": PUBLIC_DOMAIN, "hosts": [PUBLIC_DOMAIN]}

# -----------------------------------------------------------------------------------
# HTTPS / cookie / password hardening.
#
# TLS terminates at the host edge, which forwards X-Forwarded-Proto: https (the
# lowercase SECURE_PROXY_SSL_HEADER above is what Django checks). HSTS is set at
# the edge, so SECURE_HSTS_SECONDS stays 0 here to avoid duplicate headers. The
# base security headers (X-Frame-Options/X-Content-Type-Options/Referrer-Policy)
# are owned by nginx, so Django's copies are disabled to avoid conflicts.
# -----------------------------------------------------------------------------------
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Strict"
SECURE_SSL_REDIRECT = True

# TLS terminates at the ngrok edge, which does not add HSTS, so enforce it here on Django responses.
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False

# X-Frame-Options is set by nginx; Django 5.2's clickjacking middleware requires
# a string value, so drop the middleware rather than duplicate/conflict.
SECURE_CONTENT_TYPE_NOSNIFF = False
SECURE_REFERRER_POLICY = None

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

INTERNAL_IPS = ("127.0.0.1",)
DATABASES = {
    'default': dj_database_url.config(
        conn_max_age=60,
    ),
    "readonly": dj_database_url.config(
        conn_max_age=60
    )
}

# -----------------------------------------------------------------------------------
# Redis & cache - settings_common defaults these to localhost, so point them at the
# compose redis service via REDIS_URL.
# -----------------------------------------------------------------------------------
REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")
_redis = urlparse(REDIS_URL)
REDIS_HOST = _redis.hostname or "redis"
REDIS_PORT = _redis.port or 6379
REDIS_DB = int((_redis.path or "/0").lstrip("/") or 0)

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    }
}
CELERY_BROKER_URL = REDIS_URL

# -----------------------------------------------------------------------------------
# Media storage on SeaweedFS (S3-compatible). Used by org.save_media() for Surveyor uploads.
# -----------------------------------------------------------------------------------
INSTALLED_APPS = INSTALLED_APPS + ("storages",)

# Django 5.1+ replaced DEFAULT_FILE_STORAGE/STATICFILES_STORAGE with the STORAGES dict. Keep the
# inherited "archives"/"logs"/"staticfiles" entries and route file/media storage to SeaweedFS (S3).
STORAGES = {
    **STORAGES,
    "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
    "public": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
}

AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "root")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "tembatemba")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "temba-attachments")
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", "http://seaweedfs:8333")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
AWS_S3_USE_SSL = os.environ.get("AWS_S3_USE_SSL", "false").lower() in ("1", "true", "yes")
AWS_S3_ADDRESSING_STYLE = "path"
# The temba-attachments (media) bucket is made public via a bucket policy set by the
# compose seaweedfs-init service rather than per-object ACLs.
AWS_DEFAULT_ACL = None

STORAGE_URL = os.environ.get("STORAGE_URL", "http://localhost/media")

# bucket where rp-archiver writes archives and the webapp reads them from
ARCHIVE_BUCKET = os.environ.get("ARCHIVE_BUCKET", "temba-archives")

# -----------------------------------------------------------------------------------
# Mailroom - docker service. Set MAILROOM_AUTH_TOKEN (and the same value on the
# mailroom container) to require a shared token on requests.
# -----------------------------------------------------------------------------------
MAILROOM_URL = os.environ.get("MAILROOM_URL", "http://mailroom:8090")
MAILROOM_AUTH_TOKEN = os.environ.get("MAILROOM_AUTH_TOKEN") or None

# -----------------------------------------------------------------------------------
# In development, add in extra logging for exceptions and the debug toolbar
# -----------------------------------------------------------------------------------
MIDDLEWARE = ("temba.middleware.ExceptionMiddleware",) + tuple(
    m for m in MIDDLEWARE if m != "django.middleware.clickjacking.XFrameOptionsMiddleware"
)

# -----------------------------------------------------------------------------------
# Background tasks are run by the celery container, not the web thread
# -----------------------------------------------------------------------------------
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True

# -----------------------------------------------------------------------------------
# This setting throws an exception if a naive datetime is used anywhere. (they should
# always contain a timezone)
# -----------------------------------------------------------------------------------
warnings.filterwarnings(
    "error", r"DateTimeField .* received a naive datetime", RuntimeWarning, r"django\.db\.models\.fields"
)

# -----------------------------------------------------------------------------------
# Make our sitestatic URL be our static URL on development
# -----------------------------------------------------------------------------------
STATIC_URL = "/sitestatic/"
