import os
import django
from django.contrib.admin import site
from django.test import RequestFactory

# 1. Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from jobs.admin import ActiveJobAdmin, JobAdmin
from jobs.models import Job, ActiveJob

def run_simulation():
    print("🕵️‍♂️ STARTING ADMIN SIMULATION...")

    # 2. Get a real job object
    job = Job.objects.first()
    if not job:
        print("⚠️ No jobs found. Creating a dummy job...")
        job = Job.objects.create(title="Test", company="Test Co", apply_url="http://test.com")
    
    print(f"✅ Loaded Job: {job.title} (ID: {job.id})")

    # 3. Instantiate the Admin Class
    # We pass 'site' (the default admin site) to satisfy the constructor
    admin_instance = ActiveJobAdmin(ActiveJob, site)
    
    # 4. TEST 1: The Columns (list_display)
    # We manually call every method used in the Admin list to see which one breaks
    columns = ['logo_preview', 'job_card_header', 'score_display', 'tools_preview', 'open_link']
    
    print("\n🧪 Testing Admin Columns...")
    for col in columns:
        try:
            # Get the function attached to the admin class
            func = getattr(admin_instance, col)
            # Run it on the job object
            result = func(job)
            print(f"   ✅ {col}: Success")
        except Exception as e:
            print(f"   ❌ CRASH DETECTED IN '{col}'!")
            print(f"      Error: {e}")
            # We found the killer!
            return

    # 5. TEST 2: The Action Checkbox
    print("\n🧪 Testing Permissions...")
    try:
        # Check if list_editable fields crash
        if not hasattr(job, 'is_pinned'):
            raise Exception("Column 'is_pinned' missing from Model")
        if not hasattr(job, 'is_featured'):
            raise Exception("Column 'is_featured' missing from Model")
        print("   ✅ Editables: Success")
    except Exception as e:
         print(f"   ❌ CRASH IN PERMISSIONS: {e}")
         return

    print("\n🎉 SIMULATION PASSED. The Python logic is fine.")
    print("If this passed, the issue is likely a missing template or static file.")

if __name__ == '__main__':
    run_simulation()
