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

        # STRATEGY 1: Environment Variable (Best for Render)
        json_key_string = os.environ.get('GOOGLE_JSON_KEY')
        
        if json_key_string:
            try:
                info = json.loads(json_key_string)
                creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR("❌ Error: GOOGLE_JSON_KEY is not valid JSON."))
                return

        # STRATEGY 2: File (Best for Local Dev)
        else:
            key_file = os.path.join(settings.BASE_DIR, 'service_account.json')
            if os.path.exists(key_file):
                creds = service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)
            else:
                self.stdout.write(self.style.ERROR("❌ Error: Could not find GOOGLE_JSON_KEY env var OR service_account.json file."))
                return

        # Authenticate
        try:
            creds.refresh(Request())
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Auth Error: {e}"))
            return
        
        # 3. Get Jobs (Last 50 approved)
        jobs = Job.objects.filter(is_active=True, screening_status='approved')[:50]
        
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
                else:
                    self.stdout.write(self.style.ERROR(f"   ❌ Failed ({resp.status_code}): {resp.text}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ Request Error: {e}"))

        self.stdout.write("✨ Done.")
