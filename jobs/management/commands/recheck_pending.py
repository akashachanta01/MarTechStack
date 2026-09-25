"""
Put high-scoring pending jobs back live, but only when the company's own
careers site still shows them open (daily cron, right after clean_stale_jobs).

clean_stale_jobs parks 60+ day old jobs in 'pending' when nothing has confirmed
they're still open. This asks the ATS directly:
- still open            -> approved + live again (last_seen_at stamped)
- gone / closed         -> rejected ("Auto-Removed: closed on company site")
- off-topic title       -> rejected (welders etc. that scored high by mistake)
- can't tell (timeout, ATS we can't read) -> left pending for manual review

  python manage.py recheck_pending              # dry run
  python manage.py recheck_pending --confirm    # apply
"""
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone

from jobs.management.commands.audit_offtopic import OFFTOPIC_TERMS
from jobs.models import Job

OPEN, CLOSED, UNKNOWN = "open", "closed", "unknown"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MarTechJobsBot/1.0; +https://martechjobs.io)",
           "Accept": "application/json"}
_WORKDAY = re.compile(r"https://([^./]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([^/?#]+)/(job/[^?#]+)")
_GREENHOUSE = re.compile(r"greenhouse\.io/(?:embed/job_app\?for=)?([^/?#&]+)/jobs/(\d+)")
_SMARTRECRUITERS = re.compile(r"smartrecruiters\.com/([^/?#]+)/(\d+)")
_LEVER = re.compile(r"jobs\.(?:eu\.)?lever\.co/([^/?#]+)/([0-9a-f-]{36})")
_ASHBY = re.compile(r"jobs\.ashbyhq\.com/([^/?#]+)/([0-9a-f-]{36})")


def is_offtopic(title):
    t = (title or "").lower()
    return any(term in t for term in OFFTOPIC_TERMS)


def posting_status(url, timeout=10):
    """OPEN / CLOSED / UNKNOWN for a job's apply URL, from the ATS's public API."""
    url = url or ""
    try:
        m = _WORKDAY.match(url)
        if m:
            tenant, wd, site, path = m.groups()
            r = requests.get(f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/{path}",
                             headers=HEADERS, timeout=timeout)
            if r.status_code in (404, 410):
                return CLOSED
            if r.status_code != 200:
                return UNKNOWN
            info = r.json().get("jobPostingInfo") or {}
            if not info:
                return CLOSED
            return CLOSED if info.get("canApply") is False else OPEN
        m = _GREENHOUSE.search(url)
        if m:
            r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{m[1]}/jobs/{m[2]}",
                             headers=HEADERS, timeout=timeout)
            return OPEN if r.status_code == 200 else CLOSED if r.status_code == 404 else UNKNOWN
        m = _SMARTRECRUITERS.search(url)
        if m:
            r = requests.get(f"https://api.smartrecruiters.com/v1/companies/{m[1]}/postings/{m[2]}",
                             headers=HEADERS, timeout=timeout)
            if r.status_code == 404:
                return CLOSED
            if r.status_code != 200:
                return UNKNOWN
            return CLOSED if r.json().get("active") is False else OPEN
        m = _LEVER.search(url)
        if m:
            r = requests.get(f"https://api.lever.co/v0/postings/{m[1]}/{m[2]}", headers=HEADERS, timeout=timeout)
            return OPEN if r.status_code == 200 else CLOSED if r.status_code == 404 else UNKNOWN
        m = _ASHBY.search(url)
        if m:
            r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{m[1]}", headers=HEADERS, timeout=timeout)
            if r.status_code != 200:
                return UNKNOWN
            ids = {j.get("id") for j in r.json().get("jobs", [])}
            return OPEN if m[2] in ids else CLOSED
    except (requests.RequestException, ValueError):
        return UNKNOWN
    return UNKNOWN


class Command(BaseCommand):
    help = "Re-list high-scoring pending jobs that are still open on the company's site; close the rest."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", help="Apply changes (default is a dry run).")
        parser.add_argument("--min-score", type=float, default=90.0)
        parser.add_argument("--limit", type=int, default=300, help="Max jobs checked per run.")

    def handle(self, *args, **opts):
        jobs = list(Job.objects.filter(screening_status="pending", screening_score__gte=opts["min_score"])
                    .order_by("-screening_score", "-created_at")[:opts["limit"]])
        offtopic = [j for j in jobs if is_offtopic(j.title)]
        to_check = [j for j in jobs if not is_offtopic(j.title)]
        with ThreadPoolExecutor(max_workers=8) as ex:
            statuses = list(ex.map(lambda j: posting_status(j.apply_url), to_check))
        opened = [j for j, s in zip(to_check, statuses) if s == OPEN]
        closed = [j for j, s in zip(to_check, statuses) if s == CLOSED]
        unknown = [j for j, s in zip(to_check, statuses) if s == UNKNOWN]

        self.stdout.write(f"Pending jobs scored {opts['min_score']:.0f}+: {len(jobs)} | still open: {len(opened)} | "
                          f"closed: {len(closed)} | off-topic: {len(offtopic)} | couldn't check: {len(unknown)}")
        for label, group in (("↑ open", opened), ("✗ closed", closed), ("✗ off-topic", offtopic), ("? unknown", unknown)):
            for j in group:
                self.stdout.write(f"   {label}  {j.title} @ {j.company}")

        if not opts["confirm"]:
            self.stdout.write(self.style.WARNING("Dry run. Re-run with --confirm to apply."))
            return

        now = timezone.now()
        Job.objects.filter(id__in=[j.id for j in opened]).update(
            screening_status="approved", is_active=True, last_seen_at=now, updated_at=now)
        Job.objects.filter(id__in=[j.id for j in closed]).update(
            screening_status="rejected", is_active=False, updated_at=now,
            screening_reason="Auto-Removed: closed on company site")
        Job.objects.filter(id__in=[j.id for j in offtopic]).update(
            screening_status="rejected", is_active=False, updated_at=now,
            screening_reason="Auto-Removed: not a MarTech role")
        if opened:
            cache.delete("popular_tech_stacks_v4")
            cache.delete("available_countries_v4")
        self.stdout.write(self.style.SUCCESS(
            f"✅ Re-listed {len(opened)}, closed {len(closed)}, removed {len(offtopic)} off-topic, "
            f"left {len(unknown)} for review."))
