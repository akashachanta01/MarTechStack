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

# 4. FIX SEO DOMAIN (Critical for Sitemap.xml)
# This ensures Django knows the site is 'martechjobs.io', not 'example.com'
python manage.py fix_seo_domain

# 5. SEED CANONICAL TOOL PAGES
# Ensures every canonical MarTech tool (Salesforce, HubSpot, …) has a Tool row
# so /jobs/<slug>/ resolves instead of 404'ing before any job is tagged with it.
# Idempotent; empty tool pages are noindex'd by the view.
python manage.py seed_canonical_tools
