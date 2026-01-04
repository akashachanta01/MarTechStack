import os
import json
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from google.oauth2 import service_account
from google.auth.transport.requests import Request
from jobs.models import Job

class Command(BaseCommand):
    help = 'Pings Google Indexing API for all active jobs (Force Indexing)'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting Google Indexing Ping...")

        SCOPES = ["https://www.googleapis.com/auth/indexing"]
        creds = None

        # 1. Try Loading from Render Environment Variable (The Priority)
        json_key_string = os.environ.get('GOOGLE_JSON_KEY')
        
        if json_key_string:
            try:
                # Clean up the string just in case copy-paste added whitespace
                json_key_string = json_key_string.strip()
                info = json.loads(json_key_string)
                creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
                self.stdout.write("   🔑 Found GOOGLE_JSON_KEY in Environment!")
            except json.JSONDecodeError as e:
                self.stdout.write(self.style.ERROR(f"❌ Error: GOOGLE_JSON_KEY is not valid JSON. Details: {e}"))
                return
        
        # 2. Fallback to File (Local Testing)
        else:
            key_file = os.path.join(settings.BASE_DIR, 'service_account.json')
            if os.path.exists(key_file):
                creds = service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)
                self.stdout.write("   xB4 Found service_account.json file.")
            else:
                self.stdout.write(self.style.ERROR("❌ Error: Could not find GOOGLE_JSON_KEY in settings OR service_account.json file."))
                return

        # Authenticate
        try:
            creds.refresh(Request())
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Auth Error: {e}"))
            return
        
        # 3. Get Recent Jobs to Index
        jobs = Job.objects.filter(is_active=True, screening_status='approved').order_by('-created_at')[:50]
        
        if not jobs:
             self.stdout.write("   ⚠️ No active/approved jobs found to index.")
             return

        success_count = 0
        
        for job in jobs:
            url = f"{settings.DOMAIN_URL}/job/{job.id}/{job.slug}/"
            
            endpoint = "https://indexing.googleapis.com/v3/urlNotifications:publish"
            payload = {
                "url": url,
                "type": "URL_UPDATED"
            }
            
            headers = {"Authorization": f"Bearer {creds.token}"}
            try:
                resp = requests.post(endpoint, json=payload, headers=headers)
                
                if resp.status_code == 200:
                    self.stdout.write(self.style.SUCCESS(f"   ✅ Pinged: {job.title}"))
                    success_count += 1
                else:
                    self.stdout.write(self.style.ERROR(f"   ❌ Failed ({resp.status_code}): {resp.text}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ Request Error: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\n✨ Done. Successfully indexed {success_count} jobs."))
