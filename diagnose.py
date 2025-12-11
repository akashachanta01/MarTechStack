import os
import django
from django.template.loader import render_to_string
from django.conf import settings

# 1. Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from jobs.models import Job, Category

def diagnose():
    print("--- 🕵️‍♀️ STARTING DIAGNOSIS ---")
    
    # TEST 1: Database Integrity
    print("\n1. Testing Database Query...")
    try:
        jobs = Job.objects.all()
        count = jobs.count()
        print(f"✅ Database connected. Found {count} jobs.")
        
        if count > 0:
            job = jobs.first()
            print(f"   Sample Job: {job.title}")
            print(f"   Tags (Raw): {job.tags}")
            print(f"   Salary (Raw): {job.salary_range}")
            # Test the relationships which often cause crashes
            print(f"   Tools count: {job.tools.count()}") 
    except Exception as e:
        print(f"❌ DATABASE ERROR: {e}")
        return

    # TEST 2: Template Rendering (This is usually where 500s happen)
    print("\n2. Testing Template Rendering...")
    try:
        # Create fake context data like the view does
        from django.test import RequestFactory
        factory = RequestFactory()
        request = factory.get('/')
        
        context = {
            'jobs': jobs,
            'categories': Category.objects.all(),
            'current_category': None,
            'search_query': '',
            'search_loc': '',
            'is_remote': False
        }
        
        # Try to render the HTML manually
        content = render_to_string('jobs/job_list.html', context, request=request)
        print(f"✅ Template rendered successfully! (Size: {len(content)} bytes)")
        print("🎉 DIAGNOSIS: The app logic is working. The 500 error might be static files or configuration.")
        
    except Exception as e:
        print(f"❌ TEMPLATE CRASHED: {e}")
        print("\n--- ERROR DETAILS ---")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    diagnose()
