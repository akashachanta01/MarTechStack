#!/usr/bin/env bash
# Exit on error
set -o errexit

# 1. Install dependencies
pip install -r requirements.txt

# 2. Convert static files
python manage.py collectstatic --no-input

# 3. Run standard migrations
# Note: We removed 'makemigrations' because your DB is now in sync.
python manage.py migrate
