from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.core.cache import cache as django_cache

from jobs.models import Tool, Category
from jobs.tool_catalog import all_canonical_names


class Command(BaseCommand):
    help = (
        "Ensure every canonical MarTech tool has a Tool row so its /jobs/<slug>/ "
        "page exists (instead of 404'ing) even before any job is tagged with it. "
        "Idempotent. The tool_detail view noindexes pages with zero live jobs, so "
        "empty pages don't hurt SEO."
    )

    def handle(self, *args, **options):
        category, _ = Category.objects.get_or_create(
            name="MarTech", defaults={"slug": "martech"}
        )

        existing_names = {t.name.lower() for t in Tool.objects.all()}
        existing_slugs = set(Tool.objects.values_list("slug", flat=True))

        created = 0
        skipped_existing = 0
        slug_conflicts = []

        for name in sorted(all_canonical_names()):
            if name.lower() in existing_names:
                skipped_existing += 1
                continue
            slug = slugify(name)
            if slug in existing_slugs:
                # A different tool already owns this slug — don't clobber it.
                slug_conflicts.append((name, slug))
                continue
            Tool.objects.create(name=name, slug=slug, category=category)
            existing_slugs.add(slug)
            created += 1
            self.stdout.write(self.style.SUCCESS(f"  + {name}  (/jobs/{slug}/)"))

        # Bust the popular-stacks cache so new tools can surface in nav/listings.
        django_cache.delete("popular_tech_stacks_v4")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. Created {created}, already existed {skipped_existing}, "
            f"slug conflicts {len(slug_conflicts)}."
        ))
        if slug_conflicts:
            self.stdout.write(self.style.WARNING(
                "Slug already taken by another tool (left untouched):"
            ))
            for name, slug in slug_conflicts:
                self.stdout.write(f"    {name} -> {slug}")
