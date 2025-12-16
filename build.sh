#!/usr/bin/env bash
# Exit on error
set -o errexit

# 1. Install dependencies
pip install -r requirements.txt

# 2. Convert static files
python manage.py collectstatic --no-input

# 3. 🚑 EMERGENCY FIX: Manually sync DB columns
python emergency_db_sync.py

# 4. Create migrations for the changes
python manage.py makemigrations

# 5. ⚠️ FAKE MIGRATION: Mark changes as done without running SQL
# This fixes the "relation already exists" error because we manually fixed it above.
python manage.py migrate --fake jobs

# 6. Run any other standard migrations
python manage.py migrate
