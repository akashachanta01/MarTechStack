import os
import django
from django.db import connection

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from jobs.models import Job
from django.urls import reverse
from django.utils.text import slugify

def run_diagnostics():
    print("\n🔍 STARTING DIAGNOSTICS...")

    # 1. CHECK DATABASE COLUMN
    print("\n1. Checking Database Schema...")
    with connection.cursor() as cursor:
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs_job';")
        columns = [row[0] for row in cursor.fetchall()]

        if 'slug' in columns:
            print("   ✅ Column 'slug' EXISTS in database.")
        else:
            print("   ❌ Column 'slug' is MISSING.")
            print("   🛠️ Attempting emergency add...")
            try:
                cursor.execute("ALTER TABLE jobs_job ADD COLUMN slug varchar(250);")
                print("   ✅ Column added successfully.")
            except Exception as e:
                print(f"   🚨 Failed to add column: {e}")
                return

    # 2. CHECK FOR MISSING DATA (The likely cause of 500)
    print("\n2. Checking for missing slugs...")
    bad_jobs = Job.objects.filter(slug__isnull=True) | Job.objects.filter(slug='')
    count = bad_jobs.count()

    if count == 0:
        print("   ✅ All jobs have slugs.")
    else:
        print(f"   ⚠️ Found {count} jobs with missing slugs. Fixing now...")
        for job in bad_jobs:
            # Generate slug
            s = slugify(f"{job.title} {job.company}")
            if not s: s = f"job-{job.id}" 

            # Save
            job.slug = s
            job.save()
            print(f"      Fixed: {job.id} -> {s}")
        print("   ✅ Backfill complete.")

    # 3. TEST URL GENERATION (Simulate the website load)
    print("\n3. Testing Template Logic...")
    try:
        job = Job.objects.first()
        if job:
            url = reverse('job_detail', args=[job.id, job.slug])
            print(f"   ✅ SUCCESS: Generated URL for '{job.title}': {url}")
        else:
            print("   (No jobs in database to test)")
    except Exception as e:
        print(f"   ❌ CRITICAL ERROR: URL Generation failed.")
        print(f"   Error details: {e}")

    print("\n🏁 DIAGNOSTICS COMPLETE.\n")

if __name__ == '__main__':
    run_diagnostics()
