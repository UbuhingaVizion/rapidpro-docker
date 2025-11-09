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

DEBUG = True

STORAGE_URL = os.environ.get("STORAGE_URL", "http://localhost:8000/media")

# read hosts from the environment, falling back to all for dev
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "*").split(",") if h]

# read trusted origins from the environment
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

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
# In development, add in extra logging for exceptions and the debug toolbar
# -----------------------------------------------------------------------------------
MIDDLEWARE = ("temba.middleware.ExceptionMiddleware",) + MIDDLEWARE

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
