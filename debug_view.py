import os
import django
import traceback
from django.test import RequestFactory
from django.contrib.admin import site
from django.contrib.auth.models import User

# 1. Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from jobs.admin import ActiveJobAdmin
from jobs.models import ActiveJob

def run_probe():
    print("🕵️‍♂️ STARTING VIEW PROBE...")

    # 2. Ensure we have a Superuser (Admin needs one to load)
    if not User.objects.filter(is_superuser=True).exists():
        print("   ⚠️ No superuser found. Creating temp admin...")
        User.objects.create_superuser('debug_admin', 'admin@example.com', 'password')
    user = User.objects.filter(is_superuser=True).first()

    # 3. Simulate the Request
    factory = RequestFactory()
    request = factory.get('/admin/jobs/activejob/')
    request.user = user
    
    # 4. Initialize the Admin View
    model_admin = ActiveJobAdmin(ActiveJob, site)

    print("   👉 Attempting to render the 'Active Jobs' list...")

    try:
        # A. Get the Changelist Response
        response = model_admin.changelist_view(request)
        
        # B. Force it to Render (This is where templates usually crash)
        if hasattr(response, 'render'):
            response.render()
            
        print(f"   ✅ SUCCESS! Response Code: {response.status_code}")
        print("   (If you see this, the Python code is perfect. The issue is likely static files.)")

    except Exception:
        print("\n❌ CRASH DETECTED! HERE IS THE TRACEBACK:")
        print("="*60)
        traceback.print_exc()
        print("="*60)
        print("📸 COPY THE ERROR ABOVE AND PASTE IT IN THE CHAT.")

if __name__ == '__main__':
    run_probe()
