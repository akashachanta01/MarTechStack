#!/usr/bin/env bash
# Exit on error
set -o errexit

# 1. Install dependencies
pip install -r requirements.txt

# 2. Convert static files
python manage.py collectstatic --no-input

# 3. 🚑 REPAIR DATABASE: Fix missing Slug columns
python fix_slugs.py

# 4. Generate migrations on the server (GitHub-Edit Mode)
python manage.py makemigrations

# 5. Fake migrations for 'jobs' to prevent "relation already exists" errors
# This assumes fix_slugs.py and previous scripts did the heavy lifting
python manage.py migrate --fake jobs

# 6. Run any other standard migrations
python manage.py migrate
