import os
import django
from django.db import connection

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from jobs.models import Job, Tool

def diagnose():
    print("🚑 STARTING DEEP DIAGNOSIS...")
    
    # 1. Check if we can even get a job
    try:
        job = Job.objects.first()
        if not job:
            print("⚠️ No jobs in database. Try creating one to test.")
            return
        print(f"✅ Database Connection OK. Found job: {job.title}")
    except Exception as e:
        print(f"❌ CRITICAL: Cannot read 'jobs_job' table. {e}")
        return

    # 2. Test Every Column used in Admin
    # We access them one by one. The script will crash on the missing one.
    fields_to_test = [
        "screening_status",
        "work_arrangement",
        "role_type",
        "is_pinned",     # Common failure point
        "is_featured",   # Common failure point
        "plan_name",
        "screening_score",
        "tags",
        "created_at",
        "updated_at"
    ]

    print("\n🔍 Testing Columns...")
    for field in fields_to_test:
        try:
            value = getattr(job, field)
            print(f"   ✅ {field}: OK ({value})")
        except Exception as e:
            print(f"   ❌ BROKEN FIELD: '{field}' caused error: {e}")

    # 3. Test the Many-to-Many Relationship (Tools)
    print("\n🔍 Testing Relationships...")
    try:
        count = job.tools.count()
        print(f"   ✅ Tools (M2M): OK (Count: {count})")
    except Exception as e:
        print(f"   ❌ BROKEN RELATIONSHIP: 'tools' caused error: {e}")
        print("      (This means the 'jobs_job_tools' table is missing)")

    print("\n🏁 DIAGNOSIS COMPLETE.")

if __name__ == '__main__':
    diagnose()
