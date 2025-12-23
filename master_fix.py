import os
import django
from django.db import connection
from django.utils.text import slugify

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from jobs.models import Job, Tool, Category

def add_column_if_missing(table, column, definition):
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}' AND column_name = '{column}';")
        if not cursor.fetchone():
            print(f"🛠️  Adding '{column}' column to '{table}'...")
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition};")
                print("   ✅ Success.")
            except Exception as e:
                print(f"   ❌ Failed: {e}")
        else:
            print(f"✅ '{column}' column already exists in '{table}'.")

def run():
    print("\n🚑 STARTING MASTER DATABASE REPAIR...\n")

    # 1. FIX SCHEMA (Add missing columns)
    # ------------------------------------
    # Job Table
    add_column_if_missing('jobs_job', 'slug', 'varchar(250)')
    # Tool Table (This is likely the cause of your 500 error)
    add_column_if_missing('jobs_tool', 'slug', 'varchar(100)')
    # Category Table
    add_column_if_missing('jobs_category', 'slug', 'varchar(100)')

    # 2. BACKFILL DATA (Populate empty slugs)
    # ---------------------------------------
    print("\n🔄 Backfilling Data...")
    
    # Fix Jobs
    jobs = Job.objects.filter(slug__isnull=True) | Job.objects.filter(slug='')
    print(f"   - Fixing {jobs.count()} Jobs...")
    for j in jobs:
        s = slugify(f"{j.title} at {j.company}")
        if not s: s = f"job-{j.id}"
        # Ensure uniqueness
        if Job.objects.filter(slug=s).exclude(id=j.id).exists():
            s = f"{s}-{j.id}"
        j.slug = s
        j.save()

    # Fix Tools
    tools = Tool.objects.filter(slug__isnull=True) | Tool.objects.filter(slug='')
    print(f"   - Fixing {tools.count()} Tools...")
    for t in tools:
        t.slug = slugify(t.name)
        t.save()

    # Fix Categories
    cats = Category.objects.filter(slug__isnull=True) | Category.objects.filter(slug='')
    print(f"   - Fixing {cats.count()} Categories...")
    for c in cats:
        c.slug = slugify(c.name)
        c.save()

    print("\n🚀 REPAIR COMPLETE. Your site should be live.")

if __name__ == '__main__':
    run()
