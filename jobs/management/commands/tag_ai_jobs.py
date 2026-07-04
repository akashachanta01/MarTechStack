"""
Backfill the requires_ai flag on existing jobs (new jobs get it automatically
in Job.save). Run ONCE after deploying the AI & Automation category, then it's
maintained by ingest.

  python manage.py tag_ai_jobs             # dry run — shows counts + samples
  python manage.py tag_ai_jobs --confirm   # write the flags
"""

from django.core.management.base import BaseCommand

from jobs.models import Job, detect_ai_requirement


class Command(BaseCommand):
    help = "Backfill Job.requires_ai from title+description (word-boundary AI detection)."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", help="Actually write flags (default dry run).")

    def handle(self, *args, **options):
        confirm = options["confirm"]
        to_set, to_clear = [], []

        for job in Job.objects.all().only("id", "title", "description", "requires_ai").iterator():
            detected = detect_ai_requirement(job.title, job.description)
            if detected and not job.requires_ai:
                to_set.append(job.id)
            elif not detected and job.requires_ai:
                to_clear.append(job.id)

        total = Job.objects.count()
        self.stdout.write(f"Scanned {total} jobs → set requires_ai on {len(to_set)}, clear on {len(to_clear)}")

        sample = Job.objects.filter(id__in=to_set[:8]).values_list("company", "title")
        for c, t in sample:
            self.stdout.write(f"  ✓ AI: {c} | {t[:60]}")

        if not confirm:
            self.stdout.write(self.style.WARNING("Dry run — re-run with --confirm to write."))
            return

        Job.objects.filter(id__in=to_set).update(requires_ai=True)
        Job.objects.filter(id__in=to_clear).update(requires_ai=False)
        live_ai = Job.objects.filter(is_active=True, screening_status="approved", requires_ai=True).count()
        self.stdout.write(self.style.SUCCESS(f"✨ Done. Live AI-flagged jobs: {live_ai}"))
