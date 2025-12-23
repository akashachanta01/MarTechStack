import os
import django
from django.db import connection
from django.utils.text import slugify

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from jobs.models import Job

def run():
    print("🐌 STARTING SEO SLUG BACKFILL...")

    # STEP 1: Ensure the column exists (Manual Migration)
    # We do this to avoid "makemigrations" dependency on Render
    with connection.cursor() as cursor:
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs_job' AND column_name = 'slug';")
        if not cursor.fetchone():
            print("🛠️ 'slug' column missing. Adding it manually...")
            cursor.execute("ALTER TABLE jobs_job ADD COLUMN slug varchar(250);")
            print("✅ Column created.")
        else:
            print("✅ 'slug' column exists.")

    # STEP 2: Backfill Data
    jobs = Job.objects.all()
    print(f"📊 Scanning {jobs.count()} jobs...")
    
    updated = 0
    for job in jobs:
        if not job.slug:
            # Logic: Title + Company
            raw_string = f"{job.title} at {job.company}"
            new_slug = slugify(raw_string)
            
            # Fallback for empty slugs (rare)
            if not new_slug:
                new_slug = f"job-{job.id}"

            # Check uniqueness (simple version)
            # If collision, append ID
            if Job.objects.filter(slug=new_slug).exclude(id=job.id).exists():
                new_slug = f"{new_slug}-{job.id}"

            job.slug = new_slug
            job.save(update_fields=['slug'])
            print(f"   Link created: /job/{job.id}/{new_slug}")
            updated += 1
            
    print(f"\n🚀 DONE. Backfilled {updated} jobs.")

if __name__ == '__main__':
    run()
