"""
Ping IndexNow (Bing/Seznam/Yandex) with recently-changed URLs so new jobs are
indexed within minutes instead of waiting for a recrawl. ChatGPT search runs
on Bing's index, so fast Bing indexing directly improves visibility in
AI-generated answers (AEO).

Setup (one-time):
  1. Generate a key: any 32+ char hex string (e.g. `openssl rand -hex 16`).
  2. Set INDEXNOW_KEY=<key> in the Render environment (web AND cron services).
  3. The key is auto-served at https://martechjobs.io/indexnow.txt.

Runs in the daily cron after ingestion. No-ops gracefully when the key is
unset, so it's safe everywhere.

  python manage.py ping_indexnow              # jobs live in last 48h + hubs
  python manage.py ping_indexnow --hours 168  # widen the window
  python manage.py ping_indexnow --dry-run    # show URLs, don't ping
"""

import os
from datetime import timedelta

import requests
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.utils import timezone

from jobs.models import Job

DOMAIN = "https://martechjobs.io"
ENDPOINT = "https://api.indexnow.org/indexnow"


class Command(BaseCommand):
    help = "Submit recently-changed URLs to IndexNow (Bing — feeds ChatGPT search)."

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=48, help="Look-back window for new jobs (default 48).")
        parser.add_argument("--dry-run", action="store_true", help="List URLs without pinging.")

    def handle(self, *args, **options):
        key = os.environ.get("INDEXNOW_KEY", "").strip()
        if not key:
            self.stdout.write(self.style.WARNING(
                "INDEXNOW_KEY not set — skipping IndexNow ping (see command docstring for setup)."))
            return

        since = timezone.now() - timedelta(hours=options["hours"])
        new_jobs = Job.objects.filter(
            is_active=True, screening_status="approved", went_live_at__gte=since,
        ).only("id", "slug")

        urls = [f"{DOMAIN}{reverse('job_detail', args=[j.id, j.slug])}" for j in new_jobs]
        # Hub pages whose content changed because new jobs exist. Always fresh.
        urls += [
            f"{DOMAIN}/",
            f"{DOMAIN}/jobs/",
            f"{DOMAIN}/martech-job-market-statistics/",
        ]
        # IndexNow accepts up to 10,000 URLs per call; we're nowhere near.
        urls = urls[:10000]

        self.stdout.write(f"IndexNow: {len(urls)} URL(s) ({len(urls) - 3} new jobs + 3 hubs)")
        if options["dry_run"]:
            for u in urls[:20]:
                self.stdout.write(f"  {u}")
            self.stdout.write(self.style.SUCCESS("Dry run — nothing pinged."))
            return

        payload = {
            "host": "martechjobs.io",
            "key": key,
            "keyLocation": f"{DOMAIN}/indexnow.txt",
            "urlList": urls,
        }
        try:
            resp = requests.post(ENDPOINT, json=payload, timeout=15)
            # 200 = processed, 202 = accepted for processing — both fine.
            if resp.status_code in (200, 202):
                self.stdout.write(self.style.SUCCESS(f"✅ IndexNow accepted ({resp.status_code})."))
            else:
                self.stdout.write(self.style.ERROR(
                    f"❌ IndexNow returned {resp.status_code}: {resp.text[:200]}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ IndexNow ping failed: {e}"))
