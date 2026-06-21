"""
Email each active SavedSearch its NEW matching jobs from the last 24 hours.

Targeted counterpart to send_daily_digest (which emails general Subscribers).
Runs at the end of the daily cron, after fetch_jobs. Skips a search with no
new matches, so people only hear from us when there's something relevant.

  python manage.py send_saved_search_alerts            # last 24h
  python manage.py send_saved_search_alerts --dry-run  # report, don't send
"""

import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from jobs.models import Job, SavedSearch
from jobs.emails import send_html_email


class Command(BaseCommand):
    help = "Email each saved search its new matching jobs from the last 24h"

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24)
        parser.add_argument("--limit", type=int, default=12, help="Max jobs per email")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        since = timezone.now() - timedelta(hours=options["hours"])
        # Use went_live_at (when the job actually became visible) instead of
        # created_at, matching the daily digest window. A job ingested days ago
        # but only just approved should still alert; one created recently but
        # not yet live should not. Note: a job can land in both this alert and
        # the general digest within the same window — a known, accepted overlap.
        new_jobs = Job.objects.filter(
            is_active=True, screening_status="approved", went_live_at__gte=since
        ).prefetch_related("tools")

        if not new_jobs.exists():
            self.stdout.write("No new jobs in window — skipping saved-search alerts.")
            return

        searches = SavedSearch.objects.filter(is_active=True)
        total = searches.count()
        sent = 0

        for s in searches.iterator():
            qs = new_jobs
            if s.query:
                qs = qs.filter(
                    Q(title__icontains=s.query) | Q(company__icontains=s.query) | Q(tools__name__icontains=s.query)
                )
            if s.tool:
                qs = qs.filter(tools__slug=s.tool)
            if s.location:
                qs = qs.filter(location__icontains=s.location)
            if s.function:
                qs = qs.filter(function=s.function)
            if s.arrangement:
                qs = qs.filter(work_arrangement__iexact=s.arrangement)

            matches = list(qs.distinct().order_by("-created_at")[: options["limit"]])
            if not matches:
                continue

            count = len(matches)
            label = s.label or "MarTech"
            if options["dry_run"]:
                self.stdout.write(f"  {s.email} [{label}] → {count} match(es)")
                continue

            ok = send_html_email(
                subject=f"{count} new {label} role{'s' if count > 1 else ''}",
                template_name="emails/digest.html",
                context={"jobs": matches, "count": count},
                to_email=[s.email],
                unsubscribe_email=s.email,
            )
            if ok:
                s.last_notified_at = timezone.now()
                s.save(update_fields=["last_notified_at"])
                sent += 1
            time.sleep(0.3)

        if options["dry_run"]:
            self.stdout.write(self.style.SUCCESS(f"Dry run complete — {total} active searches checked."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Saved-search alerts sent to {sent}/{total} searches."))
