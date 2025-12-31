import requests
import re
from django.core.management.base import BaseCommand
from django.utils import timezone
from jobs.models import Job

class Command(BaseCommand):
    help = 'The Janitor: Scans active jobs and auto-rejects them if the link is dead, redirected, or expired.'

    def handle(self, *args, **options):
        self.stdout.write("🧹 Starting Dead Link Cleanup...")
        
        # Only check active jobs (Live on site)
        active_jobs = Job.objects.filter(is_active=True)
        total = active_jobs.count()
        dead_count = 0
        
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
            "job listing has expired",
            "search for more jobs"
        ]

        for job in active_jobs:
            reason = None
            
            try:
                # 1. STATUS CHECK
                # Allow redirects so we can catch "Job Page -> Home Page" redirects
                r = requests.get(job.apply_url, headers=headers, timeout=10, allow_redirects=True)
                
                # A. Check HTTP Codes
                if r.status_code in [404, 410]:
                    reason = f"HTTP {r.status_code} (Not Found)"
                
                # B. Check for sneaky redirects (Job Page -> generic Careers/Home page)
                # If the final URL is radically different and short (like root domain), it's suspicious
                elif len(r.url) < len(job.apply_url) * 0.5: 
                    # Heuristic: If we redirected to root or /careers, it's likely closed
                    if r.url.endswith('/') or '/careers' in r.url or '/jobs' in r.url:
                        # Only apply this if the original URL was deep (had a job ID)
                        if len(job.apply_url) > 30:
                            reason = "Redirected to Generic Page"

                # C. Check "Soft 404" (Text analysis)
                elif r.status_code == 200:
                    page_text = r.text.lower()[:5000] # Scan top of page
                    for phrase in zombie_phrases:
                        if phrase in page_text:
                            reason = f"Found phrase: '{phrase}'"
                            break

            except requests.exceptions.Timeout:
                # Be lenient on timeouts (might be temporary)
                pass
            except Exception as e:
                # Other errors (DNS, etc) might be permanent
                pass

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
