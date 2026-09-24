"""Pull Google Search Console data into the database (daily cron).

Uses the same Google service account as index_jobs (GOOGLE_JSON_KEY). Stores:
- SearchConsoleDaily: clicks / impressions / CTR / position per day (last 90 days)
- SearchConsoleRow: query x page totals for the last 28 days (replaced each run)
Search Console data lags ~2 days, so the window ends 2 days ago.
"""
import json
import os
from datetime import date, timedelta
from urllib.parse import quote

import requests
from django.core.management.base import BaseCommand
from django.db import transaction

from jobs.models import SearchConsoleDaily, SearchConsoleRow

SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
SITES = ["sc-domain:martechjobs.io", "https://martechjobs.io/", "https://www.martechjobs.io/"]
API = "https://searchconsole.googleapis.com/webmasters/v3/sites/{site}/searchAnalytics/query"


class Command(BaseCommand):
    help = "Sync Google Search Console performance data into the database."

    def handle(self, *args, **opts):
        token, email = self._token()
        if not token:
            return
        end = date.today() - timedelta(days=2)
        site = None
        for candidate in SITES:
            r = self._query(token, candidate, {"startDate": str(end - timedelta(days=89)), "endDate": str(end),
                                               "dimensions": ["date"], "rowLimit": 100})
            if r.status_code == 200:
                site, daily = candidate, r.json().get("rows", [])
                break
        if site is None:
            self.stdout.write(self.style.ERROR(
                f"❌ Search Console refused access ({r.status_code}). ACTION: Search Console → Settings → "
                f"Users and permissions → Add user → {email} (Full or Restricted)."))
            return

        r = self._query(token, site, {"startDate": str(end - timedelta(days=27)), "endDate": str(end),
                                      "dimensions": ["query", "page"], "rowLimit": 5000})
        rows = r.json().get("rows", []) if r.status_code == 200 else []

        with transaction.atomic():
            for d in daily:
                SearchConsoleDaily.objects.update_or_create(date=d["keys"][0], defaults={
                    "clicks": d.get("clicks", 0), "impressions": d.get("impressions", 0),
                    "ctr": d.get("ctr", 0), "position": d.get("position", 0)})
            if rows:
                SearchConsoleRow.objects.all().delete()
                SearchConsoleRow.objects.bulk_create([
                    SearchConsoleRow(query=x["keys"][0][:500], page=x["keys"][1][:500], clicks=x.get("clicks", 0),
                                     impressions=x.get("impressions", 0), ctr=x.get("ctr", 0),
                                     position=x.get("position", 0), period_end=end)
                    for x in rows], batch_size=1000)
        self.stdout.write(self.style.SUCCESS(
            f"✅ Search Console ({site}): {len(daily)} days, {len(rows)} query/page rows up to {end}."))

    def _token(self):
        try:
            from google.auth.transport.requests import Request
            from google.oauth2 import service_account
        except ImportError:
            self.stdout.write(self.style.WARNING("⚠️ google-auth not installed — skipping."))
            return None, ""
        raw = os.environ.get("GOOGLE_JSON_KEY", "").strip()
        if not raw:
            self.stdout.write(self.style.WARNING("⚠️ No GOOGLE_JSON_KEY — skipping Search Console sync."))
            return None, ""
        try:
            info = json.loads(raw)
            creds = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
            creds.refresh(Request())
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Google auth failed: {e}"))
            return None, ""
        return creds.token, info.get("client_email", "the service account")

    def _query(self, token, site, body):
        return requests.post(API.format(site=quote(site, safe="")), json=body,
                             headers={"Authorization": f"Bearer {token}"}, timeout=30)
