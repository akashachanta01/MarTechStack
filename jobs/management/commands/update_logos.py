import time
import os
import requests
from urllib.parse import urlparse
from django.core.management.base import BaseCommand
from jobs.models import Job

class Command(BaseCommand):
    help = 'Backfill missing company logos using Clearbit API + SerpApi Smart Search'

    def handle(self, *args, **options):
        # 1. Get API Key for smart lookups
        self.serpapi_key = os.environ.get('SERPAPI_KEY')
        if not self.serpapi_key:
            self.stdout.write(self.style.WARNING("⚠️ SERPAPI_KEY not found. Smart Google lookups will be disabled."))

        # 2. Find jobs with missing logos
        jobs = Job.objects.filter(company_logo__isnull=True) | Job.objects.filter(company_logo__exact='')
        total = jobs.count()
        
        self.stdout.write(f"🔍 Found {total} jobs missing logos. Starting update...")
        
        updated_count = 0
        
        for job in jobs:
            company_name = job.company
            if not company_name:
                continue

            # --- ATTEMPT 1: Naive Guess (Fast & Free) ---
            # Remove spaces, commas, Inc, LLC
            clean_name = company_name.lower()
            for text in [',', '.', ' inc', ' llc', ' ltd', ' corp', ' technologies', ' systems']:
                clean_name = clean_name.replace(text, '')
            
            # Force remove all whitespace (handles %20 issues)
            clean_name = "".join(clean_name.split())
            
            domains_to_try = [f"{clean_name}.com"]
            
            # --- ATTEMPT 2: Smart Search (If SerpApi is present) ---
            # If the naive guess is likely wrong (e.g. "Jasper AI"), add the search result
            if self.serpapi_key:
                real_domain = self.get_domain_from_google(company_name)
                if real_domain and real_domain != domains_to_try[0]:
                    domains_to_try.insert(0, real_domain) # Try real domain first

            logo_found = False
            for domain in domains_to_try:
                logo_url = f"https://logo.clearbit.com/{domain}"
                
                try:
                    # Check if Clearbit has it (HEAD request is faster)
                    response = requests.get(logo_url, timeout=5)
                    
                    if response.status_code == 200:
                        job.company_logo = logo_url
                        job.save(update_fields=['company_logo'])
                        self.stdout.write(self.style.SUCCESS(f"   ✅ {company_name} -> {domain}"))
                        updated_count += 1
                        logo_found = True
                        break # Stop trying domains for this job
                except Exception:
                    pass
            
            if not logo_found:
                self.stdout.write(self.style.ERROR(f"   ❌ {company_name} (Tried: {domains_to_try})"))

            # Rate limit politeness
            time.sleep(0.2)

        self.stdout.write(self.style.SUCCESS(f"\n✨ Operation Complete. Updated {updated_count}/{total} jobs."))

    def get_domain_from_google(self, company_name):
        """
        Uses SerpApi to find the official website.
        """
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
                    parsed = urlparse(link)
                    # Return domain without www (e.g. jasper.ai)
                    return parsed.netloc.replace("www.", "")
        except Exception:
            pass
        return None
