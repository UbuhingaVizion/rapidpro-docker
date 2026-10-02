#!/bin/sh
set -e

export REMOTE_CONTAINERS=true

ACTION=${1:-webapp}
VENV=/rapidpro/.venv

# The shared `sitestatic` volume may be created root-owned; make it writable for
# the unprivileged app user before dropping privileges. Only the webapp writes
# it (collectstatic); worker/beat don't mount it.
if [ "$ACTION" = "webapp" ]; then
    mkdir -p /rapidpro/sitestatic
    chown -R temba:temba /rapidpro/sitestatic
fi

if [ "$ACTION" = "webapp" ]; then
    echo "Running RapidPro webapp..."
    exec gosu temba sh -c '
        python manage.py migrate &&
        python manage.py collectstatic --noinput --clear &&
        exec gunicorn temba.wsgi:application --bind 0.0.0.0:8000 --workers 4
    '
elif [ "$ACTION" = "celery" ] || [ "$ACTION" = "worker" ]; then
    echo "Running RapidPro celery worker..."
    exec gosu temba "$VENV/bin/celery" -A temba worker -E --loglevel=INFO
elif [ "$ACTION" = "beat" ]; then
    echo "Running RapidPro celery beat..."
    exec gosu temba "$VENV/bin/celery" -A temba beat --loglevel=INFO
fi
