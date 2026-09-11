# -----------------------------------------------------------------------------------
# Docker settings for the surveyor-modern RapidPro stack.
#
# Derived from RapidPro's own temba/settings.py.dev, but wired to the docker compose
# service names (postgres/redis/minio/mailroom) and environment variables.
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
# Media storage on MinIO (S3-compatible). Used by org.save_media() for Surveyor uploads.
# -----------------------------------------------------------------------------------
INSTALLED_APPS = INSTALLED_APPS + ("storages",)

DEFAULT_FILE_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "root")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "tembatemba")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "temba-archives")
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", "http://minio:9000")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "us-east-1")
AWS_S3_USE_SSL = os.environ.get("AWS_S3_USE_SSL", "false").lower() in ("1", "true", "yes")
AWS_S3_ADDRESSING_STYLE = "path"
# MinIO buckets are made public via `mc` in the compose bucket-init service rather than
# per-object ACLs.
AWS_DEFAULT_ACL = None

STORAGE_URL = os.environ.get("STORAGE_URL", "http://localhost:9000/temba-archives")

# bucket where rp-archiver writes archives and the webapp reads them from
ARCHIVE_BUCKET = os.environ.get("ARCHIVE_BUCKET", "temba-archives")

# -----------------------------------------------------------------------------------
# Mailroom - docker service, no auth token
# -----------------------------------------------------------------------------------
MAILROOM_URL = os.environ.get("MAILROOM_URL", "http://mailroom:8090")
MAILROOM_AUTH_TOKEN = None

# -----------------------------------------------------------------------------------
# In development, add in extra logging for exceptions and the debug toolbar
# -----------------------------------------------------------------------------------
MIDDLEWARE = ("temba.middleware.ExceptionMiddleware",) + MIDDLEWARE

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
