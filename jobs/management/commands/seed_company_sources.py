"""
Backfill the CompanySource registry from existing jobs' apply URLs, so a
`fetch_jobs --sources-only` run can start direct-polling immediately instead of
waiting for the next (expensive) SERP discovery run to re-learn every board.

  python manage.py seed_company_sources             # dry run
  python manage.py seed_company_sources --confirm   # actually create rows

Parses the ATS + board token out of each job's apply_url. Idempotent: re-running
only adds boards that aren't already registered.
"""

import re

from django.core.management.base import BaseCommand

from jobs.models import Job, CompanySource


def parse_ats(url):
    """Return (ats_type, token, board_url) for a known ATS apply URL, else None."""
    if not url:
        return None
    u = url.strip()
    m = re.search(r'(?:job-boards\.|boards\.|eu\.)?greenhouse\.io/(?:embed/job_app\?for=)?([^/?#]+)', u)
    if "greenhouse.io" in u and m:
        return ("greenhouse", m.group(1), "")
    m = re.search(r'jobs\.lever\.co/([^/?#]+)', u)
    if m:
        return ("lever", m.group(1), "")
    m = re.search(r'jobs\.ashbyhq\.com/([^/?#]+)', u)
    if m:
        return ("ashby", m.group(1), "")
    m = re.search(r'apply\.workable\.com/([^/?#]+)', u) or re.search(r'([^./]+)\.workable\.com', u)
    if m and "workable.com" in u:
        return ("workable", m.group(1), "")
    m = re.search(r'jobs\.smartrecruiters\.com/([^/?#]+)', u)
    if m:
        return ("smartrecruiters", m.group(1), "")
    m = re.search(r'([^./]+)\.recruitee\.com', u)
    if m:
        return ("recruitee", m.group(1), "")
    m = re.match(r'(https?://([^.]+)\.[^.]+\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?[^/?#]+)', u)
    if m and "myworkdayjobs.com" in u:
        wm = re.match(r'https?://([^.]+)\.[^.]+\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([^/?#]+)', u)
        token = f"{wm.group(1)}/{wm.group(2)}"
        return ("workday", token, m.group(1))
    return None


class Command(BaseCommand):
    help = "Seed CompanySource registry from existing jobs' apply URLs."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", help="Actually create rows (default dry run).")

    def handle(self, *args, **options):
        confirm = options["confirm"]
        # Prefer approved jobs (boards that actually yield MarTech roles).
        urls = (
            Job.objects.filter(screening_status="approved")
            .values_list("apply_url", "company")
        )
        found = {}  # (ats_type, token) -> (name, board_url)
        for url, company in urls:
            parsed = parse_ats(url)
            if not parsed:
                continue
            ats_type, token, board_url = parsed
            key = (ats_type, token)
            if key not in found:
                found[key] = (company or token, board_url)

        existing = set(CompanySource.objects.values_list("ats_type", "token"))
        new_keys = [k for k in found if k not in existing]

        self.stdout.write(f"Parsed {len(found)} distinct boards from approved jobs; {len(new_keys)} are new.")
        by_ats = {}
        for (ats_type, token) in new_keys:
            by_ats.setdefault(ats_type, 0)
            by_ats[ats_type] += 1
        for ats_type, n in sorted(by_ats.items()):
            self.stdout.write(f"   {ats_type}: {n}")

        if not new_keys:
            self.stdout.write(self.style.SUCCESS("Registry already covers all known boards."))
            return
        if not confirm:
            self.stdout.write(self.style.WARNING(f"\nDry run. Re-run with --confirm to create {len(new_keys)} sources."))
            return

        created = 0
        for (ats_type, token) in new_keys:
            name, board_url = found[(ats_type, token)]
            _, was_created = CompanySource.objects.get_or_create(
                ats_type=ats_type, token=token,
                defaults={"name": name, "board_url": board_url},
            )
            created += 1 if was_created else 0
        self.stdout.write(self.style.SUCCESS(f"✨ Created {created} company sources."))
