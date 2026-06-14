"""
Wipe ALL jobs (and junk, non-canonical tools) for a clean re-ingestion under
the current precision/normalization logic. Destructive and irreversible —
requires --confirm to actually run.

  python manage.py reset_jobs              # dry run: shows what it WOULD delete
  python manage.py reset_jobs --confirm    # actually wipe, then re-ingest with:
                                           #   python manage.py fetch_jobs

Canonical tools (jobs.tool_catalog) are kept even with zero jobs (they'll be
re-tagged on the next ingest); non-canonical tools are removed. Subscribers,
saved searches, and blog posts are NOT touched.
"""

from django.core.management.base import BaseCommand

from jobs.models import Job, Tool
from jobs.tool_catalog import all_canonical_names


class Command(BaseCommand):
    help = "Wipe all jobs + junk tools for a clean re-ingestion (requires --confirm)"

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", help="Actually delete (otherwise dry run)")

    def handle(self, *args, **options):
        canonical = {n.lower() for n in all_canonical_names()}
        job_count = Job.objects.count()
        non_canonical = [t for t in Tool.objects.all() if (t.name or "").lower() not in canonical]

        self.stdout.write(f"Jobs to delete:        {job_count}")
        self.stdout.write(f"Non-canonical tools:   {len(non_canonical)} (canonical tools kept)")

        if not options["confirm"]:
            self.stdout.write(self.style.WARNING(
                "\nDRY RUN — nothing deleted. Re-run with --confirm to execute, then:\n"
                "   python manage.py fetch_jobs"
            ))
            return

        Job.objects.all().delete()
        deleted_tools = Tool.objects.filter(id__in=[t.id for t in non_canonical]).delete()[0]
        self.stdout.write(self.style.SUCCESS(
            f"\n🗑️ Wiped {job_count} jobs and {deleted_tools} junk tools."
        ))
        self.stdout.write("➡️  Now run a fresh ingest:  python manage.py fetch_jobs")
