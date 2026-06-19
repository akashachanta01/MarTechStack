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

        # Build name→tool map for all existing tools.
        all_tools = {t.name.lower(): t for t in Tool.objects.all()}
        existing_slugs = set(Tool.objects.values_list("slug", flat=True))

        created = 0
        slug_fixed = 0
        skipped_existing = 0
        slug_conflicts = []

        for name in sorted(all_canonical_names()):
            canonical_slug = slugify(name)
            existing = all_tools.get(name.lower())

            if existing:
                # Tool row exists — fix slug if it drifted from the canonical form.
                if existing.slug != canonical_slug:
                    if canonical_slug not in existing_slugs:
                        old_slug = existing.slug
                        existing.slug = canonical_slug
                        existing.save(update_fields=["slug"])
                        existing_slugs.discard(old_slug)
                        existing_slugs.add(canonical_slug)
                        slug_fixed += 1
                        self.stdout.write(self.style.WARNING(
                            f"  ~ {name}  slug: {old_slug} → {canonical_slug}"
                        ))
                    # else: canonical slug already taken by another row — leave it
                else:
                    skipped_existing += 1
                continue

            if canonical_slug in existing_slugs:
                # A different tool already owns this slug — don't clobber it.
                slug_conflicts.append((name, canonical_slug))
                continue
            t = Tool.objects.create(name=name, slug=canonical_slug, category=category)
            all_tools[name.lower()] = t
            existing_slugs.add(canonical_slug)
            created += 1
            self.stdout.write(self.style.SUCCESS(f"  + {name}  (/jobs/{canonical_slug}/)"))

        # Bust the popular-stacks cache so new tools can surface in nav/listings.
        django_cache.delete("popular_tech_stacks_v4")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done. Created {created}, slug fixed {slug_fixed}, "
            f"already correct {skipped_existing}, slug conflicts {len(slug_conflicts)}."
        ))
        if slug_conflicts:
            self.stdout.write(self.style.WARNING(
                "Slug already taken by another tool (left untouched):"
            ))
            for name, slug in slug_conflicts:
                self.stdout.write(f"    {name} -> {slug}")
