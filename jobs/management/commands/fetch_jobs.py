from django.core.management.base import BaseCommand
import requests
import time
import os
import re
from datetime import datetime, timedelta
from django.utils import timezone
import dateutil.parser 
from jobs.models import Job, Tool
from jobs.screener import MarTechScreener

class Command(BaseCommand):
    help = 'Auto-Discovery Job Hunter: Finds Vanity URLs and extracts hidden ATS tokens'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting Auto-Discovery Job Hunt...")
        
        self.screener = MarTechScreener()
        self.total_added = 0
        self.serpapi_key = os.environ.get('SERPAPI_KEY')
        self.cutoff_date = timezone.now() - timedelta(days=28)
        self.processed_tokens = set() # Keep track to avoid re-scanning same company
        
        if not self.serpapi_key:
            self.stdout.write(self.style.ERROR("❌ Error: Missing SERPAPI_KEY."))
            return

        self.stdout.write(f"📅 Freshness Filter: {self.cutoff_date.date()}")

        # --- HUNT TARGETS ---
        hunt_targets = [
            'Marketo', 'Salesforce Marketing Cloud', 'HubSpot', 'Braze',
            'Klaviyo', 'Iterable', 'Customer.io', 
            'Adobe Experience Platform', 'Tealium', 'mParticle', 'Real-Time CDP',
            'Google Analytics 4', 'GA4', 'Mixpanel', 'Amplitude',
            'MarTech', 'Marketing Operations', 'Marketing Technologist'
        ]

        # --- SMART QUERIES ---
        # 1. Standard: Look for boards directly
        # 2. Vanity: Look for the "footprints" left by ATS on custom domains
        search_patterns = [
            'site:boards.greenhouse.io',
            'site:jobs.lever.co',
            'site:job-boards.greenhouse.io', # Added for Pitchbook/Vultr
            'inurl:gh_jid',       # Greenhouse Job ID param (common on vanity URLs)
            'inurl:gh_src',       # Greenhouse Source param
            '"powered by greenhouse"', # Footer text footprint
            '"powered by lever"'       # Footer text footprint
        ]

        for tool in hunt_targets:
            # We combine the tool + patterns to find relevant pages
            combined_patterns = " OR ".join(search_patterns)
            query = f'"{tool}" ({combined_patterns})'
            
            self.stdout.write(f"\n🔎 Hunting: {query[:50]}...")
            
            links = self.search_google(query)
            self.stdout.write(f"   Found {len(links)} links. Analyzing...")

            for link in links:
                try:
                    self.analyze_and_fetch(link)
                    time.sleep(0.5) # Be gentle
                except Exception as e:
                    pass

        self.stdout.write(self.style.SUCCESS(f"\n✨ Done! Added {self.total_added} jobs."))

    def search_google(self, query):
        params = { "engine": "google", "q": query, "api_key": self.serpapi_key, "num": 25, "gl": "us", "hl": "en", "tbs": "qdr:m" }
        try:
            resp = requests.get("https://serpapi.com/search", params=params, timeout=10)
            return [r.get("link") for r in resp.json().get("organic_results", [])]
        except: return []

    # ==========================================
    # 🧠 THE SNIFFER: AUTO-DISCOVERY LOGIC
    # ==========================================
    def analyze_and_fetch(self, url):
        # Case 1: It's already a clean Greenhouse URL (US/EU/Job-Boards)
        if "greenhouse.io" in url:
            self.extract_and_fetch_greenhouse(url)
            return

        # Case 2: It's already a clean Lever URL
        if "jobs.lever.co" in url:
            self.extract_and_fetch_lever(url)
            return

        # Case 3: It's a Vanity URL (e.g. akqa.com) -> SNIFF IT! 🐕
        self.sniff_vanity_page(url)

    def sniff_vanity_page(self, url):
        """
        Visits a custom career page and looks for hidden tokens in the HTML.
        """
        try:
            # 1. Visit the page
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code != 200: return
            html = resp.text

            # 2. Look for Greenhouse Token Patterns
            # Pattern A: boards.greenhouse.io/TOKEN
            gh_match = re.search(r'greenhouse\.io/([^/"\'?]+)', html)
            if gh_match:
                token = gh_match.group(1)
                self.fetch_direct_greenhouse_api(token)
                return

            # Pattern B: grnhse.load_demo('TOKEN')
            gh_js_match = re.search(r'grnhse\.load_demo\([\'"]([^\'"]+)[\'"]\)', html)
            if gh_js_match:
                token = gh_js_match.group(1)
                self.fetch_direct_greenhouse_api(token)
                return

            # 3. Look for Lever Token Patterns
            lever_match = re.search(r'jobs\.lever\.co/([^/"\'?]+)', html)
            if lever_match:
                token = lever_match.group(1)
                self.fetch_direct_lever_api(token)
                return

        except Exception as e:
            pass

    # ==========================================
    # 🏭 WORKERS (API FETCHERS)
    # ==========================================
    
    def fetch_direct_greenhouse_api(self, token):
        if token in self.processed_tokens: return
        self.processed_tokens.add(token)
        
        # Try US then EU
        for domain in ["boards-api.greenhouse.io", "job-boards.eu.greenhouse.io"]:
            try:
                api_url = f"https://{domain}/v1/boards/{token}/jobs?content=true"
                resp = requests.get(api_url, timeout=5)
                if resp.status_code == 200:
                    jobs = resp.json().get('jobs', [])
                    self.stdout.write(f"      ⬇️  Fetching {len(jobs)} jobs from {token}...")
                    for item in jobs:
                        if self.is_fresh(item.get('updated_at')):
                            self.process_job(item.get('title'), token.capitalize(), item.get('location', {}).get('name'), item.get('content'), item.get('absolute_url'), "Greenhouse")
                    return # Stop if successful
            except: pass

    def fetch_direct_lever_api(self, token):
        if token in self.processed_tokens: return
        self.processed_tokens.add(token)
        try:
            api_url = f"https://api.lever.co/v0/postings/{token}?mode=json"
            resp = requests.get(api_url, timeout=5)
            if resp.status_code == 200:
                jobs = resp.json()
                self.stdout.write(f"      ⬇️  Fetching {len(jobs)} jobs from {token}...")
                for item in jobs:
                    ts = item.get('createdAt')
                    if ts:
                        dt = datetime.fromtimestamp(ts/1000.0, tz=timezone.utc)
                        if dt < self.cutoff_date: continue
                    
                    self.process_job(item.get('text'), token.capitalize(), item.get('categories', {}).get('location'), item.get('description'), item.get('hostedUrl'), "Lever")
        except: pass

    # Wrappers for direct URL processing
    def extract_and_fetch_greenhouse(self, url):
        # Handles boards.greenhouse.io, job-boards.greenhouse.io, etc.
        match = re.search(r'greenhouse\.io/([^/]+)', url)
        if match: self.fetch_direct_greenhouse_api(match.group(1))

    def extract_and_fetch_lever(self, url):
        match = re.search(r'lever\.co/([^/]+)', url)
        if match: self.fetch_direct_lever_api(match.group(1))

    # ==========================================
    # 🛠 UTILS
    # ==========================================
    def is_fresh(self, date_str):
        if not date_str: return True
        try:
            dt = dateutil.parser.parse(date_str)
            if dt.tzinfo is None: dt = timezone.make_aware(dt)
            return dt >= self.cutoff_date
        except: return True

    def process_job(self, title, company, location, description, apply_url, source):
        if Job.objects.filter(apply_url=apply_url).exists(): return
        analysis = self.screener.screen_job(title, description)
        if not analysis['is_match']: return

        categories_str = ", ".join(analysis['categories'])
        job = Job.objects.create(
            title=title, company=company, location=location or "Remote",
            description=description, apply_url=apply_url,
            tags=f"{source}, {analysis['role_type']}, {categories_str}",
            is_active=True
        )
        tool_cache = {t.name.lower(): t for t in Tool.objects.all()}
        for tool_name in analysis['stack']:
            if tool_name.lower() in tool_cache:
                job.tools.add(tool_cache[tool_name.lower()])
        self.total_added += 1
        self.stdout.write(f"         ✅ {title}")
