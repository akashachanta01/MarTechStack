import os
import django
from django.db import connection
from django.utils.text import slugify

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from jobs.models import Tool, Category

def fix_columns():
    print("🚑 STARTING DATABASE REPAIR FOR 'slugs'...")
    
    with connection.cursor() as cursor:
        # --- FIX 1: JOBS_TOOL ---
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs_tool' AND column_name = 'slug';")
        if not cursor.fetchone():
            print("🛠️ Column 'slug' missing in 'jobs_tool'. Adding...")
            # Add as nullable first so it doesn't fail on existing rows
            cursor.execute("ALTER TABLE jobs_tool ADD COLUMN slug varchar(100);")
            print("✅ Added 'slug' to jobs_tool.")
        else:
            print("✅ 'slug' already exists in jobs_tool.")
        
        # --- FIX 2: JOBS_CATEGORY ---
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs_category' AND column_name = 'slug';")
        if not cursor.fetchone():
            print("🛠️ Column 'slug' missing in 'jobs_category'. Adding...")
            cursor.execute("ALTER TABLE jobs_category ADD COLUMN slug varchar(100);")
            print("✅ Added 'slug' to jobs_category.")
        else:
            print("✅ 'slug' already exists in jobs_category.")

def populate_slugs():
    print("🔄 Populating empty slugs for Tools...")
    count = 0
    for tool in Tool.objects.all():
        if not tool.slug:
            tool.slug = slugify(tool.name)
            tool.save()
            count += 1
    print(f"   - Updated {count} tools.")

    print("🔄 Populating empty slugs for Categories...")
    count = 0
    for cat in Category.objects.all():
        if not cat.slug:
            cat.slug = slugify(cat.name)
            cat.save()
            count += 1
    print(f"   - Updated {count} categories.")

if __name__ == '__main__':
    try:
        fix_columns()
        populate_slugs()
        print("🚀 REPAIR COMPLETE.")
    except Exception as e:
        print(f"❌ Error during repair: {e}")
