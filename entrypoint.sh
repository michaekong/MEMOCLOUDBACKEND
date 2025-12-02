#!/bin/sh

echo "==============================================================="
echo "============ Remove previous migrations files ================="
echo "==============================================================="
echo ". -path "*/migrations/*.py" -not -name "__init__.py" -delete"
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
echo ". -path "*/migrations/*.pyc" -delete"
find . -path "*/migrations/*.pyc" -delete

echo "==============================================================="
echo "===================== Makemigrations =========================="
echo "==============================================================="

echo "==========> makemigrations users"
python manage.py makemigrations users

echo "==========> makemigrations transactions"
python manage.py makemigrations transactions

echo "==========> makemigrations parcelles"
python manage.py makemigrations parcelles

echo "==========> makemigrations messagerie"
python manage.py makemigrations messagerie

echo "==========> makemigrations Documents"
python manage.py makemigrations Documents

echo "done ."

echo "==============================================================="
echo "====================== Migrate ================================"
echo "==============================================================="
python manage.py migrate
echo "done ."

echo "==============================================================="
echo "================= Collect static files ========================"
echo "==============================================================="
python manage.py collectstatic --noinput
echo "==== Static files collected. Directory listing for staticfiles: ===="
ls -l $(python -c "from config.settings import STATIC_ROOT; print(STATIC_ROOT)")
echo "==== Current working directory: $(pwd) ===="

echo "done ."

echo "==============================================================="
echo "====================== Running App ============================"
echo "==============================================================="
exec daphne config.asgi:application --port 8000 --bind 0.0.0.0