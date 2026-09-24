import os
import json
import requests
from django.core.management.base import BaseCommand
from django.conf import settings
from jobs.models import Job

class Command(BaseCommand):
    help = 'Pings Google Indexing API for all active jobs (Force Indexing)'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting Google Indexing Ping...")

        # Lazy-import google-auth so a missing package never crashes the daily run.
        try:
            from google.oauth2 import service_account
            from google.auth.transport.requests import Request
        except ImportError:
            self.stdout.write(self.style.WARNING("⚠️ google-auth not installed — skipping indexing step."))
            return

        SCOPES = ["https://www.googleapis.com/auth/indexing"]
        creds = None

        # 1. Try Loading from Render Environment Variable
        json_key_string = os.environ.get('GOOGLE_JSON_KEY')

        if json_key_string:
            try:
                json_key_string = json_key_string.strip()
                info = json.loads(json_key_string)
                creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
                self.service_email = info.get('client_email', 'unknown')
                self.stdout.write("   🔑 Found GOOGLE_JSON_KEY in Environment!")
            except json.JSONDecodeError as e:
                self.stdout.write(self.style.ERROR(f"❌ Error: GOOGLE_JSON_KEY is not valid JSON. Details: {e}"))
                return
        else:
            key_file = os.path.join(settings.BASE_DIR, 'service_account.json')
            if os.path.exists(key_file):
                creds = service_account.Credentials.from_service_account_file(key_file, scopes=SCOPES)
                self.service_email = creds.service_account_email
                self.stdout.write("   📄 Found service_account.json file.")
            else:
                self.stdout.write(self.style.WARNING("⚠️ No GOOGLE_JSON_KEY env var or service_account.json — skipping indexing step."))
                return

        # Authenticate
        try:
            creds.refresh(Request())
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Auth Error: {e}"))
            return
        
        # Google's Indexing API allows ~200 notifications a day. Spend them on
        # changes only, each job once: new live jobs (URL_UPDATED) and jobs that
        # closed (URL_DELETED) so Google for Jobs stops showing dead roles.
        # screening_details records what was sent, so nothing is re-sent daily.
        from django.utils import timezone
        from datetime import timedelta
        DAILY_CAP = 180
        new_jobs = list(Job.objects.filter(
            is_active=True, screening_status='approved',
            went_live_at__gte=timezone.now() - timedelta(days=14),
        ).exclude(screening_details__has_key='index_updated').order_by('-went_live_at')[:DAILY_CAP])
        gone_jobs = list(Job.objects.filter(is_active=False, went_live_at__isnull=False)
                         .filter(screening_details__has_key='index_updated')
                         .exclude(screening_details__has_key='index_deleted')
                         .order_by('-updated_at')[:max(0, DAILY_CAP - len(new_jobs))])
        # One-time catch-up: live jobs from before this tracking existed.
        if len(new_jobs) + len(gone_jobs) < DAILY_CAP:
            new_jobs += list(Job.objects.filter(is_active=True, screening_status='approved')
                             .exclude(screening_details__has_key='index_updated')
                             .exclude(id__in=[j.id for j in new_jobs])
                             .order_by('-went_live_at')[:DAILY_CAP - len(new_jobs) - len(gone_jobs)])
        # Closed jobs that were live before tracking began also need removing.
        if len(new_jobs) + len(gone_jobs) < DAILY_CAP:
            gone_jobs += list(Job.objects.filter(is_active=False, went_live_at__isnull=False,
                                                 went_live_at__gte=timezone.now() - timedelta(days=120))
                              .exclude(screening_details__has_key='index_deleted')
                              .exclude(id__in=[j.id for j in gone_jobs])
                              .order_by('-updated_at')[:DAILY_CAP - len(new_jobs) - len(gone_jobs)])

        if not new_jobs and not gone_jobs:
            self.stdout.write("   Nothing new or closed to send to Google today.")
            return

        success_count = 0
        endpoint = "https://indexing.googleapis.com/v3/urlNotifications:publish"
        headers = {"Authorization": f"Bearer {creds.token}"}
        for job, kind, mark in [(j, "URL_UPDATED", "index_updated") for j in new_jobs] + \
                               [(j, "URL_DELETED", "index_deleted") for j in gone_jobs]:
            url = f"{settings.DOMAIN_URL}/job/{job.id}/{job.slug}/"
            try:
                resp = requests.post(endpoint, json={"url": url, "type": kind}, headers=headers, timeout=15)
                if resp.status_code == 200:
                    details = dict(job.screening_details or {})
                    details[mark] = timezone.now().isoformat()
                    Job.objects.filter(pk=job.pk).update(screening_details=details)
                    self.stdout.write(self.style.SUCCESS(f"   ✅ {kind}: {job.title}"))
                    success_count += 1
                elif resp.status_code == 403:
                    self.stdout.write(self.style.ERROR(f"   ❌ 403 PERMISSION DENIED"))
                    self.stdout.write(self.style.WARNING(f"      ACTION REQUIRED: Go to Google Search Console -> Settings -> Users."))
                    self.stdout.write(self.style.WARNING(f"      Add this email as an 'Owner': {self.service_email}"))
                    return
                elif resp.status_code == 429:
                    self.stdout.write(self.style.WARNING("   ⏸ Google daily quota reached — the rest go tomorrow."))
                    break
                else:
                    self.stdout.write(self.style.ERROR(f"   ❌ Failed ({resp.status_code}): {resp.text[:200]}"))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ Request Error: {e}"))

        self.stdout.write(self.style.SUCCESS(f"\n✨ Done. Successfully indexed {success_count} jobs."))
