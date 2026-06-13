"""
One-time cleanup: remove jobs whose apply_url points to a job AGGREGATOR
rather than the company/ATS directly. MarTechJobs promises direct-to-company
apply links, so aggregator-linked jobs (and the generic "remote marketing"
noise they carry) should not be on the board.

  python manage.py purge_aggregator_jobs --dry-run   # report only
  python manage.py purge_aggregator_jobs             # delete them
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from jobs.models import Job

# Hosts that are aggregators / not the direct employer ATS.
AGGREGATOR_HOSTS = [
    "weworkremotely.com", "remotive.com", "remoteok.com", "remoteok.io",
    "adzuna.", "jobspresso.co", "jooble.", "ziprecruiter.com", "indeed.com",
    "glassdoor.", "linkedin.com", "simplyhired.", "talent.com", "neuvoo.",
]


class Command(BaseCommand):
    help = "Delete jobs whose apply_url is an aggregator (not direct-to-company)"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report without deleting")

    def handle(self, *args, **options):
        q = Q()
        for host in AGGREGATOR_HOSTS:
            q |= Q(apply_url__icontains=host)
        matches = Job.objects.filter(q)
        total = matches.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS("✅ No aggregator-linked jobs found."))
            return

        self.stdout.write(f"Found {total} aggregator-linked job(s):")
        for j in matches[:25]:
            self.stdout.write(f"   [{j.id}] {j.title} @ {j.company} → {j.apply_url}")
        if total > 25:
            self.stdout.write(f"   …and {total - 25} more")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — nothing deleted."))
            return

        deleted = matches.delete()[0]
        self.stdout.write(self.style.SUCCESS(f"🗑️ Deleted {deleted} aggregator-linked job(s)."))
