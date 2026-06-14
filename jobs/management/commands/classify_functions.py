"""
Backfill the Job.function field (engineering / operations / data / other)
for all existing jobs using keyword + tool-slug matching.

Run once:
  python manage.py classify_functions
Re-run safely — only updates jobs where function == 'other' by default
(use --all to re-classify everything).
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from jobs.models import Job

ENGINEERING_KEYWORDS = [
    "engineer", "developer", "architect", "integration", "platform",
    "backend", "frontend", "full stack", "fullstack", "devops", "data engineer",
    "software", "technical", "implementation", "solutions engineer",
]
ENGINEERING_TOOL_SLUGS = [
    "mulesoft", "segment", "rudderstack", "snowflake", "dbt", "fivetran",
    "stitch", "airbyte", "tealium", "cdp", "customer-data-platform",
    "google-tag-manager", "gtm", "amplitude", "mixpanel", "heap",
]

OPERATIONS_KEYWORDS = [
    "operations", "ops", "admin", "administrator", "coordinator",
    "specialist", "manager", "analyst", "strategist", "consultant",
    "campaign", "crm", "email", "automation",
    "marketing ops", "martech", "demand generation",
    "demand gen", "lifecycle", "retention", "growth",
]
OPERATIONS_TOOL_SLUGS = [
    "salesforce", "hubspot", "marketo", "pardot", "eloqua", "braze",
    "iterable", "klaviyo", "mailchimp", "active-campaign", "drift",
    "intercom", "zendesk", "salesloft", "outreach", "apollo",
    "6sense", "demandbase", "terminus",
]

DATA_KEYWORDS = [
    "data", "analytics", "analyst", "bi ", "business intelligence",
    "reporting", "dashboard", "insights", "visualization", "measurement",
    "attribution", "tracking", "tag", "pixel", "seo analyst",
    "web analyst", "digital analyst",
]
DATA_TOOL_SLUGS = [
    "google-analytics", "ga4", "adobe-analytics", "looker", "tableau",
    "power-bi", "domo", "google-data-studio", "looker-studio",
    "metabase", "mode", "sigma",
]


def classify(job):
    title = (job.title or "").lower()
    tool_slugs = list(job.tools.values_list("slug", flat=True))

    scores = {"engineering": 0, "operations": 0, "data": 0}

    for kw in ENGINEERING_KEYWORDS:
        if kw in title:
            scores["engineering"] += 2
    for slug in ENGINEERING_TOOL_SLUGS:
        if any(s.startswith(slug) or slug.startswith(s) for s in tool_slugs):
            scores["engineering"] += 1

    for kw in DATA_KEYWORDS:
        if kw in title:
            scores["data"] += 2
    for slug in DATA_TOOL_SLUGS:
        if any(s.startswith(slug) or slug.startswith(s) for s in tool_slugs):
            scores["data"] += 1

    for kw in OPERATIONS_KEYWORDS:
        if kw in title:
            scores["operations"] += 2
    for slug in OPERATIONS_TOOL_SLUGS:
        if any(s.startswith(slug) or slug.startswith(s) for s in tool_slugs):
            scores["operations"] += 1

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "other"
    return best


class Command(BaseCommand):
    help = "Classify existing jobs into engineering / operations / data / other"

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Re-classify all jobs, not just unclassified ones")
        parser.add_argument("--dry-run", action="store_true", help="Print results without saving")

    def handle(self, *args, **options):
        qs = Job.objects.prefetch_related("tools")
        if not options["all"]:
            qs = qs.filter(function="other")

        total = qs.count()
        self.stdout.write(f"Classifying {total} jobs...")

        counts = {"engineering": 0, "operations": 0, "data": 0, "other": 0}
        to_update = []

        for job in qs.iterator(chunk_size=200):
            fn = classify(job)
            counts[fn] += 1
            if not options["dry_run"]:
                job.function = fn
                to_update.append(job)

            if options["dry_run"]:
                self.stdout.write(f"  [{fn:12s}] {job.title} @ {job.company}")

        if not options["dry_run"] and to_update:
            Job.objects.bulk_update(to_update, ["function"], batch_size=200)

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. engineering={counts['engineering']}, "
            f"operations={counts['operations']}, "
            f"data={counts['data']}, other={counts['other']}"
        ))
