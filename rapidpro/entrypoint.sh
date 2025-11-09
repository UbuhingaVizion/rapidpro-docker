#!/bin/sh

export REMOTE_CONTAINERS=true

ACTION=${1:-webapp}

if [ "$ACTION" = "webapp" ]; then
    echo "Running RapidPro webapp..."
	poetry run python3 manage.py migrate
    poetry run python3 manage.py collectstatic --noinput --clear
    exec poetry run gunicorn temba.wsgi:application --bind 0.0.0.0:8000 --workers 4
elif [ "$ACTION" = "celery" ]; then
    echo "Running RapidPro celery worker..."
	exec poetry run celery -A temba worker -E -B --loglevel=INFO
fi
