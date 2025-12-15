from django.core.management.base import BaseCommand
import requests
import time
import os
from jobs.models import Job, Tool
from jobs.screener import MarTechScreener

class Command(BaseCommand):
    help = 'ATS Hunter: Finds unknown companies via Google Search'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting ATS Hunter (Global Discovery)...")
        
        # 1. Setup
        self.screener = MarTechScreener()
        self.total_added = 0
        self.serpapi_key = os.environ.get('SERPAPI_KEY') # Get this from serpapi.com
        
        if not self.serpapi_key:
            self.stdout.write(self.style.ERROR("❌ Error: Missing SERPAPI_KEY environment variable."))
            return

        # 2. Define the "High Signal" Keywords to hunt for
        # We only search for the most important tools to save API credits
        hunt_targets = [
            'Marketo', 'Salesforce Marketing Cloud', 'Adobe Experience Platform',
            'Braze', 'Segment.io', 'Tealium', 'mParticle', 'HubSpot Operations'
        ]

        # 3. Define ATS Domains to scan
        ats_domains = [
            'boards.greenhouse.io',
            'jobs.lever.co',
            'jobs.ashbyhq.com'
        ]

        # --- THE HUNT LOOP ---
        for tool in hunt_targets:
            for domain in ats_domains:
                query = f'site:{domain} "{tool}"'
                self.stdout.write(f"\n🔎 Hunting for: {query}...")
                
                links = self.search_google(query)
                
                self.stdout.write(f"   found {len(links)} potential jobs...")
                
                for link in links:
                    if "greenhouse.io" in link:
                        self.fetch_greenhouse_job(link)
                    elif "lever.co" in link:
                        self.fetch_lever_job(link)
                    
                    # Be nice to rate limits
                    time.sleep(1)

        self.stdout.write(self.style.SUCCESS(f"\n✨ Hunt Complete! Added {self.total_added} new jobs."))

    # ---------------------------------------------------------
    # SEARCH ENGINE (SerpApi)
    # ---------------------------------------------------------
    def search_google(self, query):
        """Uses SerpApi to find direct ATS links"""
        params = {
            "engine": "google",
            "q": query,
            "api_key": self.serpapi_key,
            "num": 20,  # Number of results per search
            "gl": "us", # Country: US
            "hl": "en"  # Language: English
        }
        
        try:
            results = requests.get("https://serpapi.com/search", params=params, timeout=10).json()
            links = []
            if "organic_results" in results:
                for item in results["organic_results"]:
                    links.append(item.get("link"))
            return links
        except Exception as e:
            self.stdout.write(f"   ❌ Search Error: {e}")
            return []

    # ---------------------------------------------------------
    # PARSERS (Fetch content from the direct link)
    # ---------------------------------------------------------
    def fetch_greenhouse_job(self, url):
        # We need to hack the URL to get the JSON version
        # URL: https://boards.greenhouse.io/segment/jobs/12345
        # API: https://boards-api.greenhouse.io/v1/boards/segment/jobs/12345
        try:
            # Simple heuristic to extract token and ID
            parts = url.split('/')
            if 'jobs' not in parts: return
            
            token_index = parts.index('boards.greenhouse.io') + 1
            token = parts[token_index]
            job_id = parts[parts.index('jobs') + 1]

            api_url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}"
            
            resp = requests.get(api_url, timeout=5)
            if resp.status_code != 200: return
            
            data = resp.json()
            
            # Map Fields
            title = data.get('title')
            company = token.capitalize() # Greenhouse API doesn't always give company name, we infer from URL
            location = data.get('location', {}).get('name', 'Remote')
            description = data.get('content', '')
            
            self.process_job(title, company, location, description, url, "Greenhouse")
            
        except:
            pass # Skip if URL parsing fails

    def fetch_lever_job(self, url):
        # URL: https://jobs.lever.co/atlassian/123-456-789
        # API: https://api.lever.co/v0/postings/atlassian/123-456-789
        try:
            parts = url.split('/')
            if len(parts) < 5: return
            
            company = parts[3]
            job_id = parts[4]
            
            api_url = f"https://api.lever.co/v0/postings/{company}/{job_id}"
            
            resp = requests.get(api_url, timeout=5)
            if resp.status_code != 200: return
            
            data = resp.json()
            
            title = data.get('text')
            location = data.get('categories', {}).get('location', 'Remote')
            description = data.get('description', '')
            
            self.process_job(title, company.capitalize(), location, description, url, "Lever")

        except:
            pass

    # ---------------------------------------------------------
    # PROCESSOR (Shared Logic)
    # ---------------------------------------------------------
    def process_job(self, title, company, location, description, apply_url, source):
        # 1. Deduplicate
        if Job.objects.filter(apply_url=apply_url).exists():
            return

        # 2. Screen (Your Brain Logic)
        analysis = self.screener.screen_job(title, description)
        
        if not analysis['is_match']:
            return

        # 3. Save
        job = Job.objects.create(
            title=title,
            company=company,
            location=location,
            description=description,
            apply_url=apply_url,
            tags=f"{source}, {analysis['role_type']}",
            is_active=True
        )

        # 4. Link Tools
        tool_cache = {t.name.lower(): t for t in Tool.objects.all()}
        for tool_name in analysis['stack']:
            db_tool = tool_cache.get(tool_name.lower())
            if db_tool:
                job.tools.add(db_tool)
        
        self.total_added += 1
        self.stdout.write(f"      ✅ MATCH: {title} at {company}")
