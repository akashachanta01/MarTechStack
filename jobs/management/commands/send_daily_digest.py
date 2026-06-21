"""
Send a daily digest of newly-live jobs to all subscribers.

Runs after fetch_jobs in the daily cron. Uses `went_live_at` (not
`created_at`) so manually-approved jobs are caught regardless of when they
were originally ingested. The `digest_sent` flag prevents the same job from
appearing in tomorrow's digest.

Manual/testing:
  python manage.py send_daily_digest                # jobs live in last 48h
  python manage.py send_daily_digest --hours 72     # widen the window
  python manage.py send_daily_digest --dry-run      # don't send, just report
"""

import time
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from jobs.models import Job, Subscriber
from jobs.emails import send_html_email


class Command(BaseCommand):
    help = "Email subscribers a digest of jobs that went live since the last digest"

    def add_arguments(self, parser):
        parser.add_argument("--hours", type=int, default=48, help="Look-back window in hours (default 48 — safety buffer for slow-approval days)")
        parser.add_argument("--limit", type=int, default=20, help="Max jobs to include (default 20)")
        parser.add_argument("--dry-run", action="store_true", help="Report without sending")

    def handle(self, *args, **options):
        since = timezone.now() - timedelta(hours=options["hours"])
        jobs = list(
            Job.objects.filter(
                is_active=True,
                screening_status="approved",
                digest_sent=False,
                went_live_at__gte=since,
            )
            .order_by("-is_featured", "-went_live_at")[: options["limit"]]
        )

        if not jobs:
            self.stdout.write(self.style.WARNING("No new live jobs in the window — skipping digest."))
            return

        subscribers = list(Subscriber.objects.filter(is_active=True).values_list("email", flat=True))
        if not subscribers:
            self.stdout.write(self.style.WARNING("No subscribers — skipping digest."))
            return

        count = len(jobs)
        self.stdout.write(f"Daily digest: {count} new job(s) → {len(subscribers)} subscriber(s)")

        if options["dry_run"]:
            for j in jobs:
                self.stdout.write(f"  • {j.title} @ {j.company} (live: {j.went_live_at})")
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
                unsubscribe_email=email,
            )
            if ok:
                sent += 1
            time.sleep(0.3)

        # Mark these jobs so they're not re-sent tomorrow.
        if sent > 0:
            Job.objects.filter(pk__in=[j.pk for j in jobs]).update(digest_sent=True)

        self.stdout.write(self.style.SUCCESS(f"Daily digest sent to {sent}/{len(subscribers)} subscribers ({count} jobs)."))
