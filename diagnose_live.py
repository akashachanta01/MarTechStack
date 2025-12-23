import os
import django
import traceback
from django.test import RequestFactory

# 1. Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from jobs.views import job_list

def run_probe():
    print("\n🚑 LAUNCHING DIAGNOSTIC PROBE...")
    try:
        # 2. Simulate a User Request to the Homepage
        factory = RequestFactory()
        request = factory.get('/')

        # 3. Try to run the View
        print("   👉 Attempting to render homepage...")
        response = job_list(request)

        if response.status_code == 200:
            print("   ✅ SUCCESS: Homepage rendered correctly!")
        else:
            print(f"   ⚠️ WARNING: Homepage returned status {response.status_code} (Expected 200)")

    except Exception:
        # 4. CATCH AND PRINT THE HIDDEN ERROR
        print("\n❌ CRITICAL CRASH DETECTED:")
        print("-" * 60)
        traceback.print_exc()
        print("-" * 60)
        print("📸 PASTE THE ERROR ABOVE INTO THE CHAT.")

if __name__ == "__main__":
    run_probe()
