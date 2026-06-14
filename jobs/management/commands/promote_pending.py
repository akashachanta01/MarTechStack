"""
Recover GPT-approved jobs that were demoted to 'pending' only because of the
per-company anti-flooding cap (not because they're low quality).

During a fetch run, a company's roles beyond MAX_APPROVED_PER_COMPANY are parked
in 'pending' even though the screener approved them. When the cap is raised, those
jobs stay hidden (a re-fetch just sees them as duplicates). This command surfaces
them: it promotes high-scoring pending jobs to 'approved'/active, up to the cap,
counting jobs already live for that company.

  python manage.py promote_pending                 # dry run (shows what it would do)
  python manage.py promote_pending --confirm       # actually promote
  python manage.py promote_pending --confirm --min-score 85 --cap 8

Only jobs at/above --min-score (default 85 = the screener's APPROVE band) are
touched, so genuinely ambiguous (50-70) review-queue jobs are left alone.
"""

from collections import defaultdict

from django.core.management.base import BaseCommand

from jobs.models import Job


class Command(BaseCommand):
    help = "Promote high-scoring cap-demoted pending jobs back to live (up to the per-company cap)."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", help="Actually promote (default is a dry run).")
        parser.add_argument("--min-score", type=float, default=85.0, help="Only promote pending jobs at/above this score (default 85).")
        parser.add_argument("--cap", type=int, default=8, help="Max live jobs per company (default 8, matches fetch_jobs).")

    def handle(self, *args, **options):
        confirm = options["confirm"]
        min_score = options["min_score"]
        cap = options["cap"]

        # Current live count per company (so we top up to the cap, not over it).
        live_counts = defaultdict(int)
        for company in Job.objects.filter(is_active=True, screening_status="approved").values_list("company", flat=True):
            live_counts[(company or "").strip().lower()] += 1

        candidates = (
            Job.objects.filter(screening_status="pending", screening_score__gte=min_score)
            .order_by("-screening_score", "-created_at")
        )

        to_promote = []
        for job in candidates:
            ckey = (job.company or "").strip().lower()
            if live_counts[ckey] >= cap:
                continue
            to_promote.append(job)
            live_counts[ckey] += 1

        self.stdout.write(
            f"Found {candidates.count()} pending jobs >= {min_score:.0f}; "
            f"{len(to_promote)} fit under the cap of {cap}/company."
        )
        for job in to_promote:
            self.stdout.write(f"   ↑ {job.score_display() if hasattr(job, 'score_display') else int(job.screening_score)}  {job.title} @ {job.company}")

        if not to_promote:
            self.stdout.write(self.style.SUCCESS("Nothing to promote."))
            return

        if not confirm:
            self.stdout.write(self.style.WARNING(f"\nDry run. Re-run with --confirm to promote {len(to_promote)} jobs."))
            return

        ids = [j.id for j in to_promote]
        updated = Job.objects.filter(id__in=ids).update(screening_status="approved", is_active=True)
        self.stdout.write(self.style.SUCCESS(f"✨ Promoted {updated} jobs to live."))
