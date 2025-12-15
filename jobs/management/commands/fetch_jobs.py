from django.core.management.base import BaseCommand
import requests
import time
import os
from datetime import datetime, timedelta
from django.utils import timezone
import dateutil.parser 
from jobs.models import Job, Tool
from jobs.screener import MarTechScreener

class Command(BaseCommand):
    help = 'ATS Hunter: Finds ANY company using Greenhouse/Lever with Freshness Check'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting Global ATS Hunt (Last 28 Days)...")
        
        # 1. Setup
        self.screener = MarTechScreener()
        self.total_added = 0
        self.serpapi_key = os.environ.get('SERPAPI_KEY')
        
        if not self.serpapi_key:
            self.stdout.write(self.style.ERROR("❌ Error: Missing SERPAPI_KEY environment variable."))
            return

        # 2. Date Cutoff (28 Days)
        self.cutoff_date = timezone.now() - timedelta(days=28)
        self.stdout.write(f"📅 Ignoring jobs posted before: {self.cutoff_date.date()}")

        # 3. EXPANDED HUNT TARGETS 🎯
        # We search Google for these keywords specifically on ATS domains
        # 3. EXPANDED HUNT TARGETS 🎯
        # Focused on Enterprise Adobe/Salesforce + Data Infrastructure
        hunt_targets = [
            # --- Adobe Stack ---
            'Adobe Experience Platform', 'AEP',
            'Adobe Analytics', 
            'Adobe Target', 
            'Adobe Journey Optimizer', 'AJO',
            'Customer Journey Analytics', 'CJA',
            'Real-Time CDP', 'RT-CDP', 
            'Adobe Campaign', # Added: Classic enterprise tool often paired with these

            # --- Salesforce Stack ---
            'Salesforce Marketing Cloud', 'SFMC',
            'Marketo', 

            # --- Data Infrastructure ---
            'Segment.io', 
            'Tealium', 
            'mParticle', 
            'Google Tag Manager', 

            # --- Operations ---
            'HubSpot', # Broadened to match your loosened Screener

            # --- General Roles ---
            'MarTech', 
            'MarTech Architect',
            'Marketing Technology', 
            'Marketing Technologist', 
            'MarTech Developer',
            'Marketing Operations' # Added: High signal for these tools
        ]

        # 4. ATS Domains to Scan
        ats_domains = [
            'boards.greenhouse.io',
            'jobs.lever.co'
        ]

        # --- THE GLOBAL HUNT LOOP ---
        for tool in hunt_targets:
            for domain in ats_domains:
                # Example Query: site:boards.greenhouse.io "Marketo"
                query = f'site:{domain} "{tool}"'
                self.stdout.write(f"\n🔎 Hunting Google for: {query}...")
                
                links = self.search_google(query)
                self.stdout.write(f"   found {len(links)} raw links...")
                
                for link in links:
                    if "greenhouse.io" in link:
                        self.fetch_greenhouse_job(link)
                    elif "lever.co" in link:
                        self.fetch_lever_job(link)
                    
                    time.sleep(1) # Rate limit safety

        self.stdout.write(self.style.SUCCESS(f"\n✨ Hunt Complete! Added {self.total_added} fresh jobs."))

    # ---------------------------------------------------------
    # SEARCH ENGINE (SerpApi)
    # ---------------------------------------------------------
    def search_google(self, query):
        params = {
            "engine": "google",
            "q": query,
            "api_key": self.serpapi_key,
            "num": 20, # Fetch top 20 results per keyword
            "gl": "us", 
            "hl": "en",
            "tbs": "qdr:m" # Google Filter: "Past Month" (Optimization!)
        }
        try:
            resp = requests.get("https://serpapi.com/search", params=params, timeout=10)
            data = resp.json()
            links = [r.get("link") for r in data.get("organic_results", [])]
            return links
        except Exception as e:
            self.stdout.write(f"   ❌ Search Error: {e}")
            return []

    # ---------------------------------------------------------
    # PARSER: Greenhouse (With Date Check)
    # ---------------------------------------------------------
    def fetch_greenhouse_job(self, url):
        try:
            # Hack URL to get API endpoint
            parts = url.split('/')
            if 'jobs' not in parts: return
            
            token_index = parts.index('boards.greenhouse.io') + 1
            token = parts[token_index]
            job_id = parts[parts.index('jobs') + 1]

            api_url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}"
            
            resp = requests.get(api_url, timeout=5)
            if resp.status_code != 200: return
            
            data = resp.json()
            
            # 1. FRESHNESS CHECK
            if not self.is_fresh(data.get('updated_at')):
                return

            self.process_job(
                data.get('title'), 
                token.capitalize(), 
                data.get('location', {}).get('name', 'Remote'),
                data.get('content', ''), 
                url, 
                "Greenhouse"
            )
        except:
            pass 

    # ---------------------------------------------------------
    # PARSER: Lever (With Date Check)
    # ---------------------------------------------------------
    def fetch_lever_job(self, url):
        try:
            parts = url.split('/')
            if len(parts) < 5: return
            
            company = parts[3]
            job_id = parts[4]
            
            api_url = f"https://api.lever.co/v0/postings/{company}/{job_id}"
            
            resp = requests.get(api_url, timeout=5)
            if resp.status_code != 200: return
            
            data = resp.json()
            
            # 1. FRESHNESS CHECK (Lever uses 'createdAt' in ms)
            created_at = data.get('createdAt')
            if created_at:
                job_date = datetime.fromtimestamp(created_at / 1000.0, tz=timezone.utc)
                if job_date < self.cutoff_date:
                    return

            self.process_job(
                data.get('text'), 
                company.capitalize(), 
                data.get('categories', {}).get('location', 'Remote'),
                data.get('description', ''), 
                url, 
                "Lever"
            )
        except:
            pass

    # ---------------------------------------------------------
    # PROCESSOR (Screener + Saver)
    # ---------------------------------------------------------
    def process_job(self, title, company, location, description, apply_url, source):
        if Job.objects.filter(apply_url=apply_url).exists():
            return

        analysis = self.screener.screen_job(title, description)
        
        if not analysis['is_match']:
            return

        job = Job.objects.create(
            title=title,
            company=company,
            location=location,
            description=description,
            apply_url=apply_url,
            tags=f"{source}, {analysis['role_type']}",
            is_active=True
        )

        linked_count = 0
        for tool_name in analysis['stack']:
            db_tool = self.tool_cache.get(tool_name.lower())
            if db_tool:
                job.tools.add(db_tool)
                linked_count += 1
        
        self.total_added += 1
        self.stdout.write(f"      ✅ MATCH: {title} at {company}")

    def is_fresh(self, date_str):
        if not date_str: return True
        try:
            job_date = dateutil.parser.parse(date_str)
            if job_date.tzinfo is None:
                job_date = timezone.make_aware(job_date)
            return job_date >= self.cutoff_date
        except:
            return True
