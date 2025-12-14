from django.core.management.base import BaseCommand
import requests
import os
from django.utils.text import slugify
from jobs.models import Job, Tool
from jobs.screener import MarTechScreener

class Command(BaseCommand):
    help = 'Master Job Fetcher: Connects Jobs to Sidebar Tools'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting Master Job Sync (With Tool Linking)...")
        
        # Initialize
        self.screener = MarTechScreener()
        self.total_added = 0
        
        # 1. Cache all existing Tools for fast lookup
        # Creates a dictionary: {'marketo': <Tool Object>, 'sql': <Tool Object>}
        self.tool_cache = {t.name.lower(): t for t in Tool.objects.all()}
        self.stdout.write(f"ℹ️  Loaded {len(self.tool_cache)} tools from database.")

        # --- PHASE 1: GREENHOUSE DIRECT ---
        self.stdout.write(self.style.SUCCESS("\n💎 Phase 1: Scanning Premium Companies..."))
        targets = [
            'segment', 'twilio', 'webflow', 'hashicorp', 'airtable', 
            'classpass', 'figma', 'notion', 'stripe', 'plaid', 'gusto',
            'braze', 'mparticle', 'tealium', 'amplitude', 'mixpanel'
        ]
        for company in targets:
            self.fetch_greenhouse(company)

        # --- PHASE 2: ADZUNA GLOBAL ---
        self.stdout.write(self.style.SUCCESS("\n🌊 Phase 2: Scanning Global Market (Adzuna)..."))
        search_terms = ['Marketo', 'Salesforce Marketing Cloud', 'HubSpot Operations', 'Adobe Experience Platform', 'Marketing Operations']
        
        self.adzuna_id = os.environ.get('ADZUNA_ID')
        self.adzuna_key = os.environ.get('ADZUNA_KEY')

        if self.adzuna_id and self.adzuna_key:
            for term in search_terms:
                self.fetch_adzuna(term)
        
        self.stdout.write(self.style.SUCCESS(f"\n✨ Sync Complete! Total new jobs: {self.total_added}"))

    # ---------------------------------------------------------
    # WORKERS
    # ---------------------------------------------------------
    def fetch_greenhouse(self, token):
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        try:
            response = requests.get(url, timeout=5)
            if response.status_code != 200: return
            for item in response.json().get('jobs', []):
                loc = item.get('location', {}).get('name') if item.get('location') else "Remote"
                self.process_job(item.get('title'), token.capitalize(), loc, item.get('content', ''), item.get('absolute_url'), "Greenhouse")
        except: pass

    def fetch_adzuna(self, term):
        url = "http://api.adzuna.com/v1/api/jobs/us/search/1"
        params = {'app_id': self.adzuna_id, 'app_key': self.adzuna_key, 'results_per_page': 20, 'what': term, 'content-type': 'application/json'}
        try:
            resp = requests.get(url, params=params, timeout=10)
            for item in resp.json().get('results', []):
                loc = item.get('location', {}).get('display_name') if item.get('location') else "Remote"
                self.process_job(item.get('title'), item.get('company', {}).get('display_name'), loc, f"{item.get('description')}...", item.get('redirect_url'), "Adzuna")
        except: pass

    # ---------------------------------------------------------
    # PROCESSOR (The Fix is Here)
    # ---------------------------------------------------------
    def process_job(self, title, company, location, description, apply_url, source):
        # 1. Deduplicate
        if Job.objects.filter(apply_url=apply_url).exists():
            return

        # 2. Screen
        analysis = self.screener.screen_job(title, description)
        if not analysis['is_match']:
            return

        # 3. Save Job
        job = Job.objects.create(
            title=title,
            company=company,
            location=location,
            description=description,
            apply_url=apply_url,
            tags=f"{source}, {analysis['role_type']}",
            is_active=True
        )

        # 4. LINK TOOLS (The Magic Fix 🪄)
        # We look at the stack found by the screener, and find the matching DB Tool
        for tool_name in analysis['stack']:
            # Try to find the tool in our cache (fuzzy match)
            # e.g. Screener found 'marketo', DB has 'Marketo'
            db_tool = self.find_tool_in_db(tool_name)
            if db_tool:
                job.tools.add(db_tool)
        
        self.total_added += 1
        print(f"   ✅ Saved: {title} (Linked {job.tools.count()} tools)")

    def find_tool_in_db(self, tool_name):
        # Simple lookup: checks if 'marketo' matches 'Marketo' in DB
        return self.tool_cache.get(tool_name.lower())
