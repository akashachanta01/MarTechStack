import time
import re
import dateutil.parser 
import requests
from datetime import datetime, timedelta
from typing import Any, Dict
from urllib.parse import urlparse

from django.core.management.base import BaseCommand
from django.utils import timezone
from duckduckgo_search import DDGS  # <--- The Free Search Engine

from jobs.models import Job, Tool
from jobs.screener import MarTechScreener

# 🚫 BLACKLIST (Ignore these generic tokens)
BLACKLIST_TOKENS = {'embed', 'api', 'test', 'demo', 'jobs', 'careers', 'board', 'job'}

class Command(BaseCommand):
    help = 'The Free Mode Hunter: Powered by DuckDuckGo & Smart Logic'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting Job Hunt (Free Mode)...")
        
        self.screener = MarTechScreener()
        self.total_added = 0
        self.tool_cache = {self.screener._normalize(t.name): t for t in Tool.objects.all()}
        self.cutoff_date = timezone.now() - timedelta(days=28)
        self.processed_tokens = set()
        
        # --- HUNT TARGETS ---
        hunt_targets = [
            'Marketo', 'Salesforce Marketing Cloud', 'HubSpot', 
            'Braze', 'Klaviyo', 'Iterable', 'Adobe Analytics',
            'Adobe Experience Platform', 'Tealium', 'Segment', 'mParticle',
            'MarTech', 'Marketing Operations'
        ]

        # --- SMART QUERIES (Maximum Coverage) ---
        base_sites = [
            'site:boards.greenhouse.io', 'site:jobs.lever.co',
            'site:jobs.ashbyhq.com', 'site:apply.workable.com',
            'site:jobs.smartrecruiters.com'
        ]
        
        # We search site-by-site to avoid complex OR queries that DDG might dislike
        ddgs = DDGS()

        for tool in hunt_targets:
            self.stdout.write(f"\n🔎 Hunting target: {tool}...")
            
            for site in base_sites:
                query = f'{site} "{tool}"'
                
                try:
                    # DuckDuckGo Search
                    # region="wt-wt" (Global), time="m" (Past Month), max_results=25
                    results = ddgs.text(query, region='wt-wt', timelimit='m', max_results=25)
                    
                    if not results: continue

                    self.stdout.write(f"   found {len(results)} links on {site}...")

                    for res in results:
                        link = res.get('href')
                        if link:
                            self.analyze_and_fetch(link)
                            time.sleep(0.5) # Polite delay
                except Exception as e:
                    self.stdout.write(f"   ⚠️ Search Error: {e}")
                    time.sleep(2) # Backoff on error

        self.stdout.write(self.style.SUCCESS(f"\n✨ Done! Added {self.total_added} jobs."))

    # --- STEALTH HEADERS ---
    def get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/json'
        }

    # --- THE BRAIN: ANALYZE URL ---
    def analyze_and_fetch(self, url):
        # 1. Greenhouse
        if "greenhouse.io" in url and "embed" not in url:
            match = re.search(r'(?:greenhouse\.io|eu\.greenhouse\.io|job-boards\.greenhouse\.io)/([^/]+)', url)
            if match: self.fetch_greenhouse_api(match.group(1))

        # 2. Lever
        elif "lever.co" in url:
            match = re.search(r'lever\.co/([^/]+)', url)
            if match: self.fetch_lever_api(match.group(1))

        # 3. Ashby
        elif "ashbyhq.com" in url:
            match = re.search(r'jobs\.ashbyhq\.com/([^/]+)', url)
            if match: self.fetch_ashby_api(match.group(1))

        # 4. Workable
        elif "workable.com" in url:
            match = re.search(r'apply\.workable\.com/([^/]+)', url) or re.search(r'([^.]+)\.workable\.com', url)
            if match: self.fetch_workable_api(match.group(1))

    # --- API WORKERS ---

    def fetch_greenhouse_api(self, token):
        if token in self.processed_tokens or token in BLACKLIST_TOKENS: return
        self.processed_tokens.add(token)
        
        domains = ["boards-api.greenhouse.io", "job-boards.greenhouse.io"]
        for domain in domains:
            try:
                resp = requests.get(f"https://{domain}/v1/boards/{token}/jobs?content=true", headers=self.get_headers(), timeout=5)
                if resp.status_code == 200:
                    jobs = resp.json().get('jobs', [])
                    for item in jobs:
                        if self.is_fresh(item.get('updated_at')):
                            self.screen_and_upsert({
                                "title": item.get('title'), 
                                "company": token.capitalize(), 
                                "location": item.get('location', {}).get('name'), 
                                "description": item.get('content'), 
                                "apply_url": item.get('absolute_url'),
                                "remote": "remote" in item.get('location', {}).get('name', '').lower(),
                                "source": "Greenhouse"
                            })
                    return
            except: pass

    def fetch_lever_api(self, token):
        if token in self.processed_tokens: return
        self.processed_tokens.add(token)
        
        try:
            resp = requests.get(f"https://api.lever.co/v0/postings/{token}?mode=json", headers=self.get_headers(), timeout=5)
            if resp.status_code == 200:
                for item in resp.json():
                    if item.get('createdAt') and datetime.fromtimestamp(item['createdAt']/1000.0, tz=timezone.utc) >= self.cutoff_date:
                        loc = item.get('categories', {}).get('location')
                        self.screen_and_upsert({
                            "title": item.get('text'), 
                            "company": token.capitalize(), 
                            "location": loc, 
                            "description": item.get('description'), 
                            "apply_url": item.get('hostedUrl'), 
                            "remote": "remote" in (loc or "").lower(),
                            "source": "Lever"
                        })
        except: pass

    def fetch_ashby_api(self, company_name):
        if company_name in self.processed_tokens: return
        self.processed_tokens.add(company_name)
        
        try:
            resp = requests.post("https://api.ashbyhq.com/posting-api/job-board/" + company_name, headers=self.get_headers(), timeout=5)
            if resp.status_code == 200:
                jobs = resp.json().get('jobs', [])
                for item in jobs:
                    loc = item.get('location')
                    self.screen_and_upsert({
                        "title": item.get('title'),
                        "company": company_name.capitalize(),
                        "location": loc,
                        "description": f"See {item.get('jobUrl')} for details.",
                        "apply_url": item.get('jobUrl'),
                        "remote": item.get('isRemote', False) or "remote" in (loc or "").lower(),
                        "source": "Ashby"
                    })
        except: pass

    def fetch_workable_api(self, subdomain):
        if subdomain in self.processed_tokens: return
        self.processed_tokens.add(subdomain)
        
        try:
            resp = requests.get(f"https://apply.workable.com/api/v1/widget/accounts/{subdomain}", headers=self.get_headers(), timeout=5)
            if resp.status_code == 200:
                for item in resp.json().get('jobs', []):
                    if self.is_fresh(item.get('published_on')):
                        loc = f"{item.get('city', '')}, {item.get('country', '')}"
                        self.screen_and_upsert({
                            "title": item.get('title'),
                            "company": subdomain.capitalize(),
                            "location": loc,
                            "description": item.get('description'),
                            "apply_url": item.get('url'),
                            "remote": item.get('telecommuting', False),
                            "source": "Workable"
                        })
        except: pass

    # --- LOGO RESOLVER (THE FREE GOOGLE TRICK) ---
    def resolve_logo(self, company_name):
        if not company_name: return None
        # Heuristic: Clean name -> Google Favicon
        clean = company_name.lower()
        for x in [',', '.', ' inc', ' llc', ' ltd', ' corp', ' technologies', ' systems', ' group']:
            clean = clean.replace(x, '')
        clean = "".join(clean.split())
        domain = f"{clean}.com"
        return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"

    # --- SCREENING AND UPSERT ---
    def is_fresh(self, date_str):
        if not date_str: return True
        try:
            dt = dateutil.parser.parse(date_str)
            if dt.tzinfo is None: dt = timezone.make_aware(dt)
            return dt >= self.cutoff_date
        except: return True
    
    def screen_and_upsert(self, job_data: Dict[str, Any]):
        title = job_data.get("title", "")
        company = job_data.get("company", "")
        apply_url = job_data.get("apply_url", "")
        
        # Check Existence
        if Job.objects.filter(apply_url=apply_url).exists(): return

        # Resolve Logo (Free Mode)
        logo_url = self.resolve_logo(company)

        # AI Screen
        analysis = self.screener.screen(
            title=title, company=company, location=job_data.get("location", ""),
            description=job_data.get("description", ""), apply_url=apply_url
        )
        
        status = analysis.get("status", "pending")
        signals = analysis.get("details", {}).get("signals", {})

        # Save
        job = Job.objects.create(
            title=title,
            company=company,
            company_logo=logo_url,
            location=job_data.get("location", ""),
            remote=job_data.get("remote", False),
            description=job_data.get("description", ""),
            apply_url=apply_url,
            role_type=signals.get("role_type", "full_time"),
            screening_status=status,
            screening_score=analysis.get("score", 50.0),
            screening_reason=analysis.get("reason", ""),
            screening_details=analysis.get("details", {}),
            is_active=(status == "approved"),
            screened_at=timezone.now(),
            tags=f"{job_data.get('source')}, {signals.get('role_type', '')}"
        )
        
        # Link Tools
        for tool_name in signals.get("stack", []):
            t_obj = self.tool_cache.get(self.screener._normalize(tool_name))
            if t_obj: job.tools.add(t_obj)

        # Log
        if status == "approved":
            self.total_added += 1
            self.stdout.write(self.style.SUCCESS(f"   ✅ {title[:40]}.. [APPROVED]"))
        elif status == "pending":
            self.stdout.write(self.style.WARNING(f"   ⚠️ {title[:40]}.. [PENDING]"))
