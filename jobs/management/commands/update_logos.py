import time
import requests
from django.core.management.base import BaseCommand
from jobs.models import Job

class Command(BaseCommand):
    help = 'Backfill missing company logos using Clearbit API'

    def handle(self, *args, **options):
        # Find jobs with empty or null logos
        jobs = Job.objects.filter(company_logo__isnull=True) | Job.objects.filter(company_logo__exact='')
        total = jobs.count()
        
        self.stdout.write(f"🔍 Found {total} jobs missing logos. Starting update...")
        
        updated_count = 0
        
        for job in jobs:
            company_name = job.company
            if not company_name:
                continue

            # 1. Heuristic Domain Guessing
            # Convert "HubSpot, Inc." -> "hubspot"
            clean_name = company_name.lower().replace(',', '').replace('.', '').replace(' inc', '').replace(' llc', '').replace(' ltd', '').strip()
            clean_name = clean_name.replace(' ', '') # "stack adapt" -> "stackadapt"
            
            domain_guess = f"{clean_name}.com"
            logo_url = f"https://logo.clearbit.com/{domain_guess}"

            self.stdout.write(f"   Checking {company_name} -> {logo_url}...", ending='')

            try:
                # 2. Verify the logo exists (Head request is faster)
                response = requests.get(logo_url, timeout=3)
                
                if response.status_code == 200:
                    job.company_logo = logo_url
                    job.save(update_fields=['company_logo'])
                    self.stdout.write(self.style.SUCCESS(" ✅ Found & Saved"))
                    updated_count += 1
                else:
                    self.stdout.write(self.style.WARNING(" ❌ Not found"))
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f" Error: {e}"))

            # Rate limit politeness
            time.sleep(0.2)

        self.stdout.write(self.style.SUCCESS(f"\n✨ Operation Complete. Updated {updated_count}/{total} jobs."))
