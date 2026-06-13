"""
Send a daily digest of newly-posted jobs to all subscribers.

Designed to run at the end of the daily ingestion cron (run_daily_tasks),
right after fetch_jobs, so subscribers get one email per day covering the
roles added that day. Skips quietly when there are no new jobs.

Routes through emails.send_html_email so every message gets the
List-Unsubscribe / one-click headers and a personalized unsubscribe link —
critical for a bulk send to stay out of spam.

Manual/testing:
  python manage.py send_daily_digest                # last 24h
  python manage.py send_daily_digest --hours 48     # widen the window
  python manage.py send_daily_digest --dry-run      # don't send, just report
"""

import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from jobs.models import Job, Subscriber
from jobs.emails import send_html_email


class Command(BaseCommand):
    help = "Email subscribers a digest of jobs posted in the last 24 hours"

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=24, help="Look-back window in hours (default 24)")
        parser.add_argument("--limit", type=int, default=20, help="Max jobs to include (default 20)")
        parser.add_argument("--dry-run", action="store_true", help="Report without sending")

    def handle(self, *args, **options):
        since = timezone.now() - timedelta(hours=options["hours"])
        jobs = list(
            Job.objects.filter(
                is_active=True,
                screening_status="approved",
                created_at__gte=since,
            )
            .order_by("-is_featured", "-created_at")[: options["limit"]]
        )

        if not jobs:
            self.stdout.write(self.style.WARNING("No new jobs in the window — skipping digest."))
            return

        subscribers = list(Subscriber.objects.values_list("email", flat=True))
        if not subscribers:
            self.stdout.write(self.style.WARNING("No subscribers — skipping digest."))
            return

        count = len(jobs)
        self.stdout.write(f"Daily digest: {count} new job(s) → {len(subscribers)} subscriber(s)")

        if options["dry_run"]:
            for j in jobs:
                self.stdout.write(f"  • {j.title} @ {j.company}")
            self.stdout.write(self.style.SUCCESS("Dry run — nothing sent."))
            return

        subject = f"New MarTech roles — {count} added today" if count > 1 else "A new MarTech role was just posted"
        sent = 0
        for email in subscribers:
            ok = send_html_email(
                subject=subject,
                template_name="emails/digest.html",
                context={"jobs": jobs, "count": count},
                to_email=[email],
                unsubscribe_email=email,  # personalized one-click unsubscribe
            )
            if ok:
                sent += 1
            time.sleep(0.3)  # gentle pacing for SMTP / reputation

        self.stdout.write(self.style.SUCCESS(f"Daily digest sent to {sent}/{len(subscribers)} subscribers."))
