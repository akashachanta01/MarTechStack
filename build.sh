#!/usr/bin/env bash
# Exit on error
set -o errexit

# 1. Install dependencies
pip install -r requirements.txt

# 2. Convert static files
python manage.py collectstatic --no-input

# 3. 🚑 REPAIR DATABASE: Add missing columns manually
python fix_updated_at.py

# 4. Generate migrations on the server (Since you edit in GitHub)
python manage.py makemigrations

# 5. Fake the migration for 'jobs' so Django doesn't try to add the column again
# We do this because we just added it manually above!
python manage.py migrate --fake jobs

# 6. Run any other standard migrations
python manage.py migrate
