"""
Re-runs the screener on recently rejected jobs. Useful after tightening
the screener to recover false negatives (roles wrongly rejected).

  python manage.py rescreen_rejected              # dry run — shows candidates
  python manage.py rescreen_rejected --confirm    # re-screen and promote passing jobs
  python manage.py rescreen_rejected --days 60    # look back 60 days (default 30)
  python manage.py rescreen_rejected --limit 300  # cap batch size
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from jobs.models import Job
from jobs.screener import MarTechScreener


class Command(BaseCommand):
    help = "Re-screen recently rejected jobs to recover false negatives."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", help="Actually re-screen (default is dry run).")
        parser.add_argument("--days", type=int, default=30, help="Look back N days (default 30).")
        parser.add_argument("--limit", type=int, default=300, help="Max jobs to process (default 300).")

    def handle(self, *args, **options):
        confirm = options["confirm"]
        days = options["days"]
        limit = options["limit"]

        cutoff = timezone.now() - timedelta(days=days)
        candidates = list(
            Job.objects.filter(
                screening_status="rejected",
                updated_at__gte=cutoff,
            ).order_by("-created_at")[:limit]
        )

        self.stdout.write(f"Found {len(candidates)} rejected jobs from last {days} days to re-screen.")

        if not confirm:
            self.stdout.write(self.style.WARNING(f"\nDry run. Re-run with --confirm to re-screen {len(candidates)} jobs."))
            return

        screener = MarTechScreener()
        promoted = 0
        still_rejected = 0

        for job in candidates:
            result = screener.screen(
                title=job.title,
                company=job.company,
                location=job.location or "",
                description=job.description or "",
                apply_url=job.apply_url or "",
            )
            status = result.get("status")
            score = result.get("score", 0)

            job.screening_status = status
            job.screening_score = score
            job.screening_reason = result.get("reason", "")
            job.save(update_fields=["screening_status", "screening_score", "screening_reason", "updated_at"])

            if status == "approved":
                job.is_active = True
                job.save(update_fields=["is_active"])
                promoted += 1
                self.stdout.write(self.style.SUCCESS(f"  ✅ {job.company}: {job.title}"))
            else:
                still_rejected += 1

        self.stdout.write(f"\n✨ Promoted: {promoted} | Still rejected: {still_rejected}")
