from django.core.management.base import BaseCommand
import requests
import os
from jobs.models import Job
from jobs.screener import MarTechScreener

class Command(BaseCommand):
    help = 'Master Job Fetcher: Greenhouse (Premium) + Adzuna (Global) + Python Screener'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting Master Job Sync...")
        
        # Initialize the Screener Engine
        self.screener = MarTechScreener()
        self.total_added = 0

        # --- PHASE 1: GREENHOUSE DIRECT (High Quality) ---
        self.stdout.write(self.style.SUCCESS("\n💎 Phase 1: Scanning Premium Companies..."))
        # Add as many as you want here. Google "companies using Greenhouse"
        targets = [
            'segment', 'twilio', 'webflow', 'hashicorp', 'airtable', 
            'classpass', 'figma', 'notion', 'stripe', 'plaid', 'gusto',
            'braze', 'mparticle', 'tealium', 'amplitude', 'mixpanel'
        ]
        
        for company in targets:
            self.fetch_greenhouse(company)

        # --- PHASE 2: ADZUNA GLOBAL (High Volume) ---
        self.stdout.write(self.style.SUCCESS("\n🌊 Phase 2: Scanning Global Market (Adzuna)..."))
        
        # We search for the TOOLS to find random companies
        search_terms = [
            'Marketo', 'Salesforce Marketing Cloud', 'HubSpot Operations', 
            'Adobe Experience Platform', 'Marketing Technologist', 'Marketing Operations',
            'Marketing Data Analyst', 'Revenue Operations'
        ]
        
        self.adzuna_id = os.environ.get('ADZUNA_ID')
        self.adzuna_key = os.environ.get('ADZUNA_KEY')

        if self.adzuna_id and self.adzuna_key:
            for term in search_terms:
                self.fetch_adzuna(term)
        else:
            self.stdout.write(self.style.WARNING("⚠️ Adzuna ID/Key missing. Skipping Phase 2."))

        self.stdout.write(self.style.SUCCESS(f"\n✨ Sync Complete! Total new jobs: {self.total_added}"))

    # ---------------------------------------------------------
    # WORKER: GREENHOUSE
    # ---------------------------------------------------------
    def fetch_greenhouse(self, token):
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200: return

            jobs = response.json().get('jobs', [])
            for item in jobs:
                # Greenhouse usually has Location inside an object
                loc_name = "Remote"
                if item.get('location') and item.get('location').get('name'):
                    loc_name = item.get('location').get('name')

                if self.process_job(
                    title=item.get('title'),
                    company=token.capitalize(),
                    location=loc_name,
                    description=item.get('content', ''), # Full HTML
                    apply_url=item.get('absolute_url'),
                    source="Greenhouse"
                ):
                    print(f"   ✅ {token}: {item.get('title')}")

        except Exception:
            pass # Fail silently on individual companies

    # ---------------------------------------------------------
    # WORKER: ADZUNA
    # ---------------------------------------------------------
    def fetch_adzuna(self, term):
        url = "http://api.adzuna.com/v1/api/jobs/us/search/1"
        params = {
            'app_id': self.adzuna_id,
            'app_key': self.adzuna_key,
            'results_per_page': 20, 
            'what': term,
            'content-type': 'application/json'
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                print(f"   ⚠️ Adzuna Error: {resp.status_code}")
                return

            results = resp.json().get('results', [])
            for item in results:
                # Adzuna Location handling
                loc_name = "Remote"
                if item.get('location') and item.get('location').get('display_name'):
                    loc_name = item.get('location').get('display_name')

                if self.process_job(
                    title=item.get('title'),
                    company=item.get('company', {}).get('display_name', 'Unknown'),
                    location=loc_name,
                    description=f"{item.get('description')}...", # Snippet
                    apply_url=item.get('redirect_url'),
                    source="Adzuna"
                ):
                    print(f"   ✅ Adzuna ({term}): {item.get('title')}")
        except Exception as e:
            print(f"Adzuna Logic Error: {e}")

    # ---------------------------------------------------------
    # SHARED PROCESSOR (Where the Screener lives)
    # ---------------------------------------------------------
    def process_job(self, title, company, location, description, apply_url, source):
        # 1. Deduplicate
        if Job.objects.filter(apply_url=apply_url).exists():
            return False

        # 2. SCREEN IT (The Logic)
        analysis = self.screener.screen_job(title, description)
        
        if not analysis['is_match']:
            return False

        # 3. PREPARE TAGS
        # Convert list ['SQL', 'Python'] to string "SQL, Python"
        stack_tags = ", ".join(analysis['stack'][:5])
        role_tag = analysis['role_type']
        final_tags = f"{stack_tags}, {role_tag}, {source}"

        # 4. SAVE
        Job.objects.create(
            title=title,
            company=company,
            location=location,
            description=description,
            apply_url=apply_url,
            tags=final_tags,
            is_active=True
        )
        self.total_added += 1
        return True
