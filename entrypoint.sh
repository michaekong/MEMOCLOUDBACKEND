#!/bin/sh

# -------------------------------
# Entrypoint Django Production
# -------------------------------

set -e  # Stop script on first error

echo "---------------------------------"
echo "Applying Django migrations (fake-initial)..."
echo "---------------------------------"
# --fake-initial : ignore les tables déjà créées
python manage.py migrate --fake-initial

echo "---------------------------------"
echo "Collecting static files..."
echo "---------------------------------"
python manage.py collectstatic --noinput

# Vérifier le contenu du dossier static (optionnel)
STATIC_DIR=$(python -c "from config.settings import STATIC_ROOT; print(STATIC_ROOT)")
if [ -d "$STATIC_DIR" ]; then
    echo "Static files in $STATIC_DIR:"
    ls -l "$STATIC_DIR"
fi

echo "---------------------------------"
echo "Starting Django server..."
echo "---------------------------------"
# Utiliser exec pour remplacer le shell et ne pas bloquer le container
exec python3 manage.py runserver 0.0.0.0:8000