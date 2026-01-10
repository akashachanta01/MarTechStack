import os
import django
from django.db import connection

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def nuke_conflicts():
    print("🔧 Cleaning up database conflicts...")
    with connection.cursor() as cursor:
        # 1. Drop conflicting columns from 'jobs_job'
        # We drop these so migration 0006 can recreate them cleanly.
        job_cols = [
            'is_featured', 'is_pinned', 'plan_name', 'role_type', 
            'salary_range', 'work_arrangement', 'tags', 'slug', 'updated_at'
        ]
        
        print("   --- Cleaning Job Model ---")
        for col in job_cols:
            try:
                # We use CASCADE to remove any dependent indexes automatically
                cursor.execute(f"ALTER TABLE jobs_job DROP COLUMN IF EXISTS {col} CASCADE;")
                print(f"   ✅ Dropped column: jobs_job.{col}")
            except Exception as e:
                print(f"   ⚠️ Could not drop jobs_job.{col}: {e}")

        # 2. Drop conflicting columns from 'jobs_tool' (SEO fields)
        tool_cols = ['seo_title', 'seo_h1']
        
        print("   --- Cleaning Tool Model ---")
        for col in tool_cols:
            try:
                cursor.execute(f"ALTER TABLE jobs_tool DROP COLUMN IF EXISTS {col} CASCADE;")
                print(f"   ✅ Dropped column: jobs_tool.{col}")
            except Exception as e:
                print(f"   ⚠️ Could not drop jobs_tool.{col}: {e}")

        # 3. Ensure Subscriber table is gone (to prevent DuplicateTable error)
        cursor.execute("DROP TABLE IF EXISTS jobs_subscriber CASCADE;")
        print("   ✅ Ensured jobs_subscriber table is removed.")

    print("\n✨ Database is clean. You can now run 'python manage.py migrate'.")

if __name__ == "__main__":
    nuke_conflicts()
