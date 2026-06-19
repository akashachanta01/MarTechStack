"""
Re-runs the AI screener on jobs that have screening_score=25 (the
crash-fallback score set when OpenAI is unavailable or returns an error).
These jobs passed the keyword gate but were never properly scored.

  python manage.py rescreen_crashed              # dry run — shows count
  python manage.py rescreen_crashed --confirm    # actually re-screens
  python manage.py rescreen_crashed --confirm --limit 50   # batch of 50
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from jobs.models import Job
from jobs.screener import MarTechScreener


class Command(BaseCommand):
    help = "Re-screen pending jobs that scored 25 (AI crash fallback) now that OpenAI is healthy."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", help="Actually re-screen (default is a dry run).")
        parser.add_argument("--limit", type=int, default=200, help="Max jobs to process per run (default 200).")

    def handle(self, *args, **options):
        confirm = options["confirm"]
        limit = options["limit"]

        candidates = list(
            Job.objects.filter(
                screening_status="pending",
                screening_score=25.0,
            ).order_by("-created_at")[:limit]
        )

        self.stdout.write(f"Found {len(candidates)} score-25 pending jobs to re-screen.")

        if not confirm:
            self.stdout.write(self.style.WARNING(f"\nDry run. Re-run with --confirm to process {len(candidates)} jobs."))
            return

        screener = MarTechScreener()
        approved = rejected = still_pending = errors = 0

        for job in candidates:
            try:
                result = screener.screen(
                    job.title or "",
                    job.company or "",
                    job.location or "",
                    job.description or "",
                    job.apply_url or "",
                )
                status = result.get("status", "pending")
                score = float(result.get("score", 25.0))

                job.screening_status = status
                job.screening_score = score
                job.screening_reason = result.get("reason", "")
                job.screening_details = result.get("details", {})
                job.screened_at = timezone.now()
                job.is_active = (status == "approved")
                job.save(update_fields=[
                    "screening_status", "screening_score", "screening_reason",
                    "screening_details", "screened_at", "is_active",
                ])

                if status == "approved":
                    approved += 1
                    self.stdout.write(self.style.SUCCESS(f"  ✅ {score:.0f}  {job.title} @ {job.company}"))
                elif status == "rejected":
                    rejected += 1
                    self.stdout.write(f"  ✗  {score:.0f}  {job.title} @ {job.company}")
                else:
                    still_pending += 1
                    self.stdout.write(self.style.WARNING(f"  ?  {score:.0f}  {job.title} @ {job.company}"))

            except Exception as e:
                errors += 1
                self.stdout.write(self.style.ERROR(f"  ❌ Error on {job.title}: {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"\n✨ Done. Approved: {approved}  Rejected: {rejected}  "
            f"Still pending: {still_pending}  Errors: {errors}"
        ))
