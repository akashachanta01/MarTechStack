import time
import os
import requests
from urllib.parse import urlparse
from django.core.management.base import BaseCommand
from jobs.models import Job

class Command(BaseCommand):
    help = 'Backfill missing company logos using Smart Search + Google Fallback'

    def handle(self, *args, **options):
        self.serpapi_key = os.environ.get('SERPAPI_KEY')
        
        # 1. Find jobs with missing logos
        jobs = Job.objects.filter(company_logo__isnull=True) | Job.objects.filter(company_logo__exact='')
        total = jobs.count()
        
        self.stdout.write(f"🔍 Found {total} jobs missing logos. Starting update...")
        
        # Headers to prevent 403 blocks
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        updated_count = 0
        
        for job in jobs:
            company_name = job.company
            if not company_name: continue

            # --- STEP 1: RESOLVE DOMAIN ---
            domain = self.resolve_domain(company_name)
            
            if not domain:
                self.stdout.write(self.style.WARNING(f"   ⚠️ Could not resolve domain for: {company_name}"))
                continue

            # --- STEP 2: FETCH LOGO (Dual-Engine) ---
            logo_url = None
            
            # Engine A: Clearbit
            clearbit_url = f"https://logo.clearbit.com/{domain}"
            try:
                resp = requests.get(clearbit_url, headers=headers, timeout=3)
                if resp.status_code == 200:
                    logo_url = clearbit_url
            except: pass

            # Engine B: Google Favicon (Fallback)
            if not logo_url:
                google_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=128"
                # Google almost always returns 200, even for default icons, so we just use it.
                logo_url = google_url

            # --- STEP 3: SAVE ---
            if logo_url:
                job.company_logo = logo_url
                job.save(update_fields=['company_logo'])
                self.stdout.write(self.style.SUCCESS(f"   ✅ {company_name} -> {domain} -> Saved"))
                updated_count += 1
            else:
                self.stdout.write(self.style.ERROR(f"   ❌ Failed to find logo for {domain}"))

            # Polite delay
            time.sleep(0.2)

        self.stdout.write(self.style.SUCCESS(f"\n✨ Operation Complete. Updated {updated_count}/{total} jobs."))

    def resolve_domain(self, company_name):
        """
        Returns the best guess for the company domain.
        Priority: SerpApi > Heuristic Guess
        """
        # 1. Clean the name for heuristic
        clean_name = company_name.lower()
        for text in [',', '.', ' inc', ' llc', ' ltd', ' corp', ' technologies', ' systems', ' group']:
            clean_name = clean_name.replace(text, '')
        clean_name = "".join(clean_name.split()) # Remove all spaces
        
        heuristic_domain = f"{clean_name}.com"

        # 2. Try SerpApi if available (Best for 'Jasper AI' -> 'jasper.ai')
        if self.serpapi_key:
            try:
                params = { 
                    "engine": "google", 
                    "q": f"{company_name} official site", 
                    "api_key": self.serpapi_key, 
                    "num": 1 
                }
                resp = requests.get("https://serpapi.com/search", params=params, timeout=5)
                if resp.status_code == 200:
                    results = resp.json().get("organic_results", [])
                    if results:
                        link = results[0].get("link")
                        return urlparse(link).netloc.replace("www.", "")
            except: 
                pass
        
        # 3. Fallback to heuristic
        return heuristic_domain
