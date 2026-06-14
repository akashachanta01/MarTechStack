"""
Delete junk Tool rows: non-canonical tools that have NO live jobs. These are
left over from earlier ingestion (e.g. "ssf", "paid-media-data", "crm",
"signal-validation") and create thin /jobs/<slug>/ pages Google indexes.

Canonical tools (jobs.tool_catalog) and any tool that still has live jobs are
kept (the latter are only noindex'd, never deleted, so we don't untag jobs).

  python manage.py cleanup_junk_tools --dry-run
  python manage.py cleanup_junk_tools
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from jobs.models import Tool
from jobs.tool_catalog import all_canonical_names


class Command(BaseCommand):
    help = "Delete non-canonical Tool rows that have no live jobs"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        canonical = {n.lower() for n in all_canonical_names()}
        tools = Tool.objects.annotate(
            live=Count("jobs", filter=Q(jobs__is_active=True, jobs__screening_status="approved"))
        )
        junk = [t for t in tools if t.live == 0 and (t.name or "").lower() not in canonical]

        if not junk:
            self.stdout.write(self.style.SUCCESS("✅ No junk tools to remove."))
            return

        self.stdout.write(f"Found {len(junk)} junk tool(s) (non-canonical, 0 live jobs):")
        for t in junk:
            self.stdout.write(f"   [{t.id}] {t.name} (/jobs/{t.slug}/)")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run — nothing deleted."))
            return

        ids = [t.id for t in junk]
        deleted = Tool.objects.filter(id__in=ids).delete()[0]
        self.stdout.write(self.style.SUCCESS(f"🗑️ Deleted {deleted} junk tool row(s)."))
