#!/usr/bin/env bash
# Exit on error
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Convert static files
python manage.py collectstatic --no-input

# ⚠️ GITHUB-EDIT HACK: Create migrations on the server since we don't do it locally
# Only keep this while you are actively changing DB models.
python manage.py makemigrations

# Run database migrations
python manage.py migrate
