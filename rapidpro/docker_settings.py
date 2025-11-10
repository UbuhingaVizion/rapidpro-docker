# -----------------------------------------------------------------------------------
# Sample RapidPro settings file, this should allow you to deploy RapidPro locally on
# a PostgreSQL database.
#
# The following are requirements:
#     - a postgreSQL database named 'temba', with a user name 'temba' and
#       password 'temba' (with postgis extensions installed)
#     - a redis instance listening on localhost
# -----------------------------------------------------------------------------------

import warnings
import os
import dj_database_url
from .settings_common import *  # noqa
from .settings_security import *  # noqa

DEBUG = os.environ.get("DJANGO_DEBUG", "False").lower() in ("true", "1")

# use the header defined in docker-compose, e.g. "HTTP_X_FORWARDED_PROTO,https"
_proxy_header = os.environ.get("DJANGO_SECURE_PROXY_SSL_HEADER")
if _proxy_header:
    SECURE_PROXY_SSL_HEADER = tuple(_proxy_header.split(","))

STORAGE_URL = os.environ.get("STORAGE_URL", "http://localhost:8000/media")

# read hosts from the environment, falling back to all for dev
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]

# read trusted origins from the environment
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

# if not set via env, derive from allowed hosts
if not CSRF_TRUSTED_ORIGINS and ALLOWED_HOSTS and ALLOWED_HOSTS != ["*"]:
    CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS]

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
# Mailroom - localhost for dev, no auth token
# -----------------------------------------------------------------------------------
MAILROOM_URL = os.environ.get("MAILROOM_URL", "http://localhost:8090")
MAILROOM_AUTH_TOKEN = None

# -----------------------------------------------------------------------------------
# In production, we don't want the debug exception middleware
# -----------------------------------------------------------------------------------
if not DEBUG:
    MIDDLEWARE = tuple(m for m in MIDDLEWARE if m != "temba.middleware.ExceptionMiddleware")

# -----------------------------------------------------------------------------------
# In development, perform background tasks in the web thread (synchronously)
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

# -----------------------------------------------------------------------------------
# Firebase stuff
#
# This is the legacy FCM API key used by the FirebaseCloudMessagingType channel.
# This is different from the service account key used by Mailroom for Android sync.
# -----------------------------------------------------------------------------------

FCM_API_KEY= os.environ.get("FCM_API_KEY", "")

# -----------------------------------------------------------------------------------
# Override the public IP addresses from the environment
# This is required for channel types that use IP whitelisting.
# -----------------------------------------------------------------------------------
_ip_addresses = os.environ.get("RAPIDPRO_IP_ADDRESSES")
if _ip_addresses:
    IP_ADDRESSES = tuple(ip.strip() for ip in _ip_addresses.split(","))

# -----------------------------------------------------------------------------------
# Email settings from environment
# -----------------------------------------------------------------------------------
if os.environ.get("DJANGO_EMAIL_HOST"):
    SEND_EMAILS = os.environ.get("DJANGO_SEND_EMAILS", "True").lower() in ("true", "1")
    EMAIL_HOST = os.environ.get("DJANGO_EMAIL_HOST")
    EMAIL_PORT = int(os.environ.get("DJANGO_EMAIL_PORT", "587"))
    EMAIL_USE_TLS = os.environ.get("DJANGO_EMAIL_USE_TLS", "True").lower() in ("true", "1")
    EMAIL_HOST_USER = os.environ.get("DJANGO_EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = os.environ.get("DJANGO_EMAIL_HOST_PASSWORD")
    DEFAULT_FROM_EMAIL = os.environ.get("DJANGO_DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
