#!/bin/sh

set -e  # Stop script on first error

echo "Cleaning old migrations..."
find . -path "*/migrations/*.py" -not -name "__init__.py" -print -delete
find . -path "*/migrations/*.pyc" -print -delete

echo "Creating migrations..."
python manage.py makemigrations

echo "Applying migrations..."
python manage.py migrate

echo "Collecting static files..."
python manage.py collectstatic --noinput
STATIC_DIR=$(python -c "from config.settings import STATIC_ROOT; print(STATIC_ROOT)")
[ -d "$STATIC_DIR" ] && ls -l "$STATIC_DIR"

echo "Starting Django server..."
exec python3 manage.py runserver 0.0.0.0:8000