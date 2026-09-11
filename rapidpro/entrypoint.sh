#!/bin/sh

export REMOTE_CONTAINERS=true

ACTION=${1:-webapp}
VENV=/rapidpro/.venv

if [ "$ACTION" = "webapp" ]; then
    echo "Running RapidPro webapp..."
    "$VENV/bin/python" manage.py migrate
    "$VENV/bin/python" manage.py collectstatic --noinput --clear
    exec "$VENV/bin/gunicorn" temba.wsgi:application --bind 0.0.0.0:8000 --workers 4
elif [ "$ACTION" = "celery" ]; then
    echo "Running RapidPro celery worker..."
    exec "$VENV/bin/celery" -A temba worker -E -B --loglevel=INFO
fi
