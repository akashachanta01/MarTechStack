import time
import re
import dateutil.parser 
import requests
import os
from datetime import datetime, timedelta
from typing import Any, Dict
from urllib.parse import urlparse

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from jobs.models import Job, Tool
from jobs.screener import MarTechScreener

# 🚫 BLACKLIST
BLACKLIST_TOKENS = {'embed', 'api', 'test', 'demo', 'jobs', 'careers', 'board', 'job'}
REMOTE_KEYWORDS = {'remote', 'anywhere', 'global', 'work from home', 'wfh'}
HYBRID_KEYWORDS = {'hybrid', 'flexible', 'flex', 'part-time remote', 'in-office required', 'partial remote', 'blended'} # 💥 NEW

class Command(BaseCommand):
    help = 'The Enterprise Hunter: SerpApi (Paid) + Multi-ATS Support + External Config'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting Job Hunt (Enterprise Mode)...")
        
        # 1. Load API Key
        self.serpapi_key = os.environ.get('SERPAPI_KEY')
        if not self.serpapi_key:
            self.stdout.write(self.style.ERROR("❌ Error: Missing SERPAPI_KEY environment variable."))
            return

        self.screener = MarTechScreener()
        self.total_added = 0
        self.tool_cache = {self.screener._normalize(t.name): t for t in Tool.objects.all()}
        self.cutoff_date = timezone.now() - timedelta(days=28)
        self.processed_tokens = set()
        
        # --- LOAD TARGETS FROM FILE ---
        hunt_targets = []
        target_file_path = os.path.join(settings.BASE_DIR, 'hunt_targets.txt')
        
        if os.path.exists(target_file_path):
            self.stdout.write(f"📂 Loading targets from: {target_file_path}")
            with open(target_file_path, 'r') as f:
                hunt_targets = [line.strip() for line in f if line.strip()]
        
        # Fallback if file is missing or empty
        if not hunt_targets:
            self.stdout.write(self.style.WARNING("⚠️ No targets found in file. Using hardcoded defaults."))
            hunt_targets = [
                'Marketo', 'Salesforce Marketing Cloud', 'HubSpot', 
                'Braze', 'Klaviyo', 'Iterable', 'Adobe Analytics',
                'Adobe Experience Platform', 'Tealium', 'Segment', 'mParticle',
                'MarTech', 'Marketing Operations'
            ]

        # --- SMART QUERIES ---
        base_sites = (
            'site:boards.greenhouse.io OR site:jobs.lever.co OR '
            'site:jobs.ashbyhq.com OR site:apply.workable.com OR '
            'site:jobs.smartrecruiters.com'
        )

        for tool in hunt_targets:
            if tool.startswith('#'): continue

            query = f'"{tool}" ({base_sites})'
            self.stdout.write(f"\n🔎 Hunting: {tool}...")
            
            # SERPAPI SEARCH
            links = self.search_google(query)
            self.stdout.write(f"   Found {len(links)} links. Analyzing...")

            for link in links:
                try:
                    self.analyze_and_fetch(link)
                    time.sleep(0.2)
                except Exception as e:
                    pass

        self.stdout.write(self.style.SUCCESS(f"\n✨ Done! Added {self.total_added} jobs."))

    # --- LOCATION CLEANUP HELPER (Globally Aware + Hybrid Detection) ---
    def _clean_location(self, location_str, is_remote_flag):
        if not location_str:
            return "On-site", 'onsite'
        
        # Normalize
        clean_loc = location_str.strip().replace(' | ', ', ').replace('/', ', ').replace('(', '').replace(')', '')
        loc_lower = clean_loc.lower()
        arrangement = 'onsite'

        # 1. Determine base arrangement
        if is_remote_flag or any(k in loc_lower for k in REMOTE_KEYWORDS):
            arrangement = 'remote'

        # 2. Check for HYBRID keywords (can override remote)
        if any(k in loc_lower for k in HYBRID_KEYWORDS):
            arrangement = 'hybrid'

        # Safely remove work-style keywords from the actual location string
        all_work_keywords = REMOTE_KEYWORDS.union(HYBRID_KEYWORDS).union({'onsite', 'remote'})
        location_parts = [
            part.strip() for part in clean_loc.split(',') 
            if part.strip() and not any(k in part.strip().lower() for k in all_work_keywords)
        ]
        
        final_location = ", ".join(location_parts)
        
        if not final_location:
            # If all location parts were keywords, return the arrangement type as the location
            return arrangement.capitalize(), arrangement
        
        return final_location, arrangement

    # --- SERPAPI ENGINE (Unchanged) ---
    def search_google(self, query):
        params = { 
            "engine": "google", 
            "q": query, 
            "api_key": self.serpapi_key, 
            "num": 30,  
            "gl": "us", 
            "hl": "en", 
            "tbs": "qdr:m"
        }
        try:
            resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
            if resp.status_code == 200:
                results = resp.json().get("organic_results", [])
                return [r.get("link") for r in results]
            else:
                self.stdout.write(self.style.WARNING(f"   ⚠️ SerpApi Error: {resp.status_code}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ⚠️ Connection Error: {e}"))
        return []

    # --- HEADERS (Unchanged) ---
    def get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/json'
        }

    # --- THE BRAIN: ANALYZE URL (Unchanged) ---
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

    # --- API WORKERS (UPDATED for work_arrangement) ---

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
                            raw_loc = item.get('location', {}).get('name')
                            is_remote_check = "remote" in (raw_loc or "").lower()
                            clean_loc, work_arrangement = self._clean_location(raw_loc, is_remote_check)

                            self.screen_and_upsert({
                                "title": item.get('title'), 
                                "company": token.capitalize(), 
                                "location": clean_loc, 
                                "description": item.get('content'), 
                                "apply_url": item.get('absolute_url'),
                                "work_arrangement": work_arrangement, # 💥 Changed from "remote"
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
                        raw_loc = item.get('categories', {}).get('location')
                        is_remote_check = "remote" in (raw_loc or "").lower()
                        clean_loc, work_arrangement = self._clean_location(raw_loc, is_remote_check)

                        self.screen_and_upsert({
                            "title": item.get('text'), 
                            "company": token.capitalize(), 
                            "location": clean_loc, 
                            "description": item.get('description'), 
                            "apply_url": item.get('hostedUrl'), 
                            "work_arrangement": work_arrangement, # 💥 Changed from "remote"
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
                    raw_loc = item.get('location')
                    is_remote_check = item.get('isRemote', False)
                    clean_loc, work_arrangement = self._clean_location(raw_loc, is_remote_check)
                    
                    self.screen_and_upsert({
                        "title": item.get('title'),
                        "company": company_name.capitalize(),
                        "location": clean_loc,
                        "description": f"See {item.get('jobUrl')} for details.",
                        "apply_url": item.get('jobUrl'),
                        "work_arrangement": work_arrangement, # 💥 Changed from "remote"
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
                        raw_loc = f"{item.get('city', '')}, {item.get('country', '')}"
                        is_remote_check = item.get('telecommuting', False)
                        clean_loc, work_arrangement = self._clean_location(raw_loc, is_remote_check)

                        self.screen_and_upsert({
                            "title": item.get('title'),
                            "company": subdomain.capitalize(),
                            "location": clean_loc,
                            "description": item.get('description'),
                            "apply_url": item.get('url'),
                            "work_arrangement": work_arrangement, # 💥 Changed from "remote"
                            "source": "Workable"
                        })
        except: pass

    # --- LOGO RESOLVER (Unchanged) ---
    def resolve_logo(self, company_name):
        if not company_name: return None
        clean = company_name.lower()
        for x in [',', '.', ' inc', ' llc', ' ltd', ' corp', ' technologies', ' systems', ' group']:
            clean = clean.replace(x, '')
        clean = "".join(clean.split())
        domain = f"{clean}.com"
        return f"https://www.google.com/s2/favicons?domain={domain}&sz=128"

    # --- SCREENING AND UPSERT (UPDATED for work_arrangement) ---
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
        
        if Job.objects.filter(apply_url=apply_url).exists(): return

        logo_url = self.resolve_logo(company)

        analysis = self.screener.screen(
            title=title, company=company, location=job_data.get("location", ""),
            description=job_data.get("description", ""), apply_url=apply_url
        )
        
        status = analysis.get("status", "pending")
        signals = analysis.get("details", {}).get("signals", {})

        job = Job.objects.create(
            title=title,
            company=company,
            company_logo=logo_url,
            location=job_data.get("location", ""),
            work_arrangement=job_data.get("work_arrangement", "onsite"), # 💥 Changed from "remote"
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
        
        for tool_name in signals.get("stack", []):
            t_obj = self.tool_cache.get(self.screener._normalize(tool_name))
            if t_obj: job.tools.add(t_obj)

        if status == "approved":
            self.total_added += 1
            self.stdout.write(self.style.SUCCESS(f"   ✅ {title[:40]}.. [APPROVED]"))
        elif status == "pending":
            self.stdout.write(self.style.WARNING(f"   ⚠️ {title[:40]}.. [PENDING]"))
