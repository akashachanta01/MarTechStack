import requests
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db.models import F
from django.utils import timezone
from jobs.models import Job
from jobs.management.commands.recheck_pending import posting_status, OPEN, CLOSED

class Command(BaseCommand):
    help = 'The Janitor: Scans active jobs and auto-rejects them if the link is dead, redirected, or expired.'

    def handle(self, *args, **options):
        self.stdout.write("🧹 Starting Dead Link Cleanup...")

        # Ask the ATS's own API first (Workday/Greenhouse/Lever/SmartRecruiters/
        # Ashby): Workday pages are JavaScript shells that look "open" to a page
        # scrape even after the job closes, so the scrape alone removed 0/100 a day
        # (Oct 2026 audit: 137 live Workday jobs unconfirmed for 8+ days).
        # Least-recently confirmed first; jobs their board listed in the last 2
        # days are skipped (fetch_jobs already confirmed them).
        now = timezone.now()
        active_jobs = list(Job.objects.filter(is_active=True, created_at__lte=now - timedelta(days=3))
                           .exclude(last_seen_at__gte=now - timedelta(days=2))
                           .order_by(F('last_seen_at').asc(nulls_first=True))[:200])
        total = len(active_jobs)
        dead_count = 0
        with ThreadPoolExecutor(max_workers=8) as ex:
            api_status = dict(zip([j.id for j in active_jobs], ex.map(lambda j: posting_status(j.apply_url), active_jobs)))
        confirmed = [j.id for j in active_jobs if api_status[j.id] == OPEN]
        Job.objects.filter(id__in=confirmed).update(last_seen_at=now)
        self.stdout.write(f"   Company sites confirm {len(confirmed)} still open.")

        self.stdout.write(f"   Scanning {total} active jobs...")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        # "Zombie Phrases" - If we see these, the job is likely dead even if status is 200 OK
        zombie_phrases = [
            "job is no longer available", 
            "this position has been filled", 
            "no longer accepting applications", 
            "page you are looking for doesn't exist",
            "job listing has expired"
        ]

        scrapes_left = 80  # sequential page reads, 10s timeout each: keeps the step under its 20-min budget
        for job in active_jobs:
            if api_status[job.id] == OPEN:
                continue
            if api_status[job.id] == CLOSED:
                reason = "Closed on company site"
            elif scrapes_left > 0:
                scrapes_left -= 1
                reason = self._scrape_reason(job, headers, zombie_phrases)
            else:
                continue

            # 2. ACTION: REJECT IF DEAD
            if reason:
                job.screening_status = 'rejected'
                job.is_active = False
                job.screening_reason = f"Auto-Removed: {reason}"
                job.save()
                
                self.stdout.write(self.style.WARNING(f"   🚫 Removed: {job.title} ({reason})"))
                dead_count += 1
            else:
                # Optional: Simple dot to show progress
                self.stdout.write(".", ending="")

        self.stdout.write(self.style.SUCCESS(f"\n✨ Cleanup Complete. Removed {dead_count}/{total} dead jobs."))

    def _scrape_reason(self, job, headers, zombie_phrases):
        """Fallback for ATSs without a public API: read the apply page itself."""
        try:
            # Allow redirects so we can catch "Job Page -> Home Page" redirects
            r = requests.get(job.apply_url, headers=headers, timeout=10, allow_redirects=True)
            if r.status_code in [404, 410]:
                return f"HTTP {r.status_code} (Not Found)"
            # Redirected from a deep job URL to a short generic careers/home page
            if len(r.url) < len(job.apply_url) * 0.5:
                if (r.url.endswith('/') or '/careers' in r.url or '/jobs' in r.url) and len(job.apply_url) > 30:
                    return "Redirected to Generic Page"
            elif r.status_code == 200:
                page_text = r.text.lower()[:5000]  # Scan top of page
                for phrase in zombie_phrases:
                    if phrase in page_text:
                        return f"Found phrase: '{phrase}'"
        except requests.exceptions.Timeout:
            pass  # temporary; don't penalise
        except requests.exceptions.ConnectionError:
            return "Connection failed (board may be removed)"  # DNS failure / refused: board is gone
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"\n   ⚠ Check error for {job.apply_url}: {e}"))
        return None
