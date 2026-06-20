"""
Management command to fix SEO metadata for key blog posts based on GSC data.
Run once: python manage.py fix_blog_seo
"""
from django.core.management.base import BaseCommand
from jobs.models import BlogPost


class Command(BaseCommand):
    help = "Fix meta_title and meta_description for key blog posts based on GSC data."

    def handle(self, *args, **options):
        updates = [
            {
                "slug": "martech-job-titles-career-paths",
                "title": "MarTech Job Titles & Roles Classification Guide 2026",
                "meta_title": "MarTech Job Titles & Roles Classification Guide 2026",
                "meta_description": (
                    "Complete MarTech roles classification — Marketing Ops, Marketing Automation, "
                    "Analytics, CDP and Engineering titles explained. Find your next role on MarTechJobs."
                ),
            },
        ]

        for item in updates:
            updated = BlogPost.objects.filter(slug=item["slug"]).update(
                title=item["title"],
                meta_title=item["meta_title"],
                meta_description=item["meta_description"],
            )
            if updated:
                self.stdout.write(self.style.SUCCESS(
                    f"Updated '{item['slug']}': {updated} row(s)"
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"No blog post found with slug '{item['slug']}' — skipping."
                ))
