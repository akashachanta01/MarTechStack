"""
Retire junk Tool rows that aren't in the canonical MarTech catalog.

These are the source of the low-quality, noindex'd tool pages (e.g. "crm",
"ssf", "paid-media-data") that ingestion used to auto-create. With the whitelist
now enforced on both ingestion and user submission, no NEW junk is produced;
this command cleans up the historical rows so their thin pages stop existing.

Deleting a Tool only removes its job<->tool links (the jobs themselves stay);
it just detaches the bad tag and removes the /jobs/<slug>/ page.

Dry-run by default. Pass --confirm to actually delete.
"""

from django.core.management.base import BaseCommand
from django.db.models import Count

from jobs.models import Tool
from jobs.tool_catalog import all_canonical_names


class Command(BaseCommand):
    help = "Delete Tool rows whose name is not in the canonical catalog (junk pages)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm", action="store_true",
            help="Actually delete. Without this flag, only reports what would be deleted.",
        )

    def handle(self, *args, **options):
        canonical = {n.lower() for n in all_canonical_names()}
        junk = (Tool.objects.annotate(n_jobs=Count("jobs"))
                .exclude(name__in=[n for n in all_canonical_names()]))
        # Robust case-insensitive filter (the exclude above is case-sensitive on
        # some DBs); re-filter in Python against the lowercased canonical set.
        junk = [t for t in junk if t.name.lower() not in canonical]

        if not junk:
            self.stdout.write(self.style.SUCCESS("✅ No non-canonical tools found. Nothing to prune."))
            return

        total_links = sum(t.n_jobs for t in junk)
        self.stdout.write(f"Found {len(junk)} non-canonical tools "
                          f"({total_links} job links would be detached):")
        for t in sorted(junk, key=lambda x: -x.n_jobs):
            self.stdout.write(f"   - {t.name}  (slug={t.slug}, jobs={t.n_jobs})")

        if not options["confirm"]:
            self.stdout.write(self.style.WARNING(
                "\nDry run. Re-run with --confirm to delete these tools."))
            return

        ids = [t.id for t in junk]
        deleted, _ = Tool.objects.filter(id__in=ids).delete()
        from django.core.cache import cache
        cache.delete("popular_tech_stacks_v4")
        self.stdout.write(self.style.SUCCESS(
            f"\n🧹 Deleted {len(ids)} non-canonical tools ({deleted} rows incl. relations)."))
