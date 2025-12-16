import json
import os
import time
import re
import dateutil.parser 
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from jobs.models import Job, Tool, Category
from jobs.screener import MarTechScreener

# 🚫 BLACKLIST (Ignore these generic tokens)
BLACKLIST_TOKENS = {'embed', 'api', 'test', 'demo', 'jobs', 'careers', 'board'}

class Command(BaseCommand):
    help = 'The Gold Standard Hunter: AI-Powered Edition with Multi-ATS Support'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting AI Job Hunt...")
        
        self.screener = MarTechScreener()
        self.total_added = 0
        self.serpapi_key = os.environ.get('SERPAPI_KEY')
        
        if not self.serpapi_key:
            self.stdout.write(self.style.ERROR("❌ Error: Missing SERPAPI_KEY."))
            return

        self.tool_cache = {self.screener._normalize(t.name): t for t in Tool.objects.all()}
        self.cutoff_date = timezone.now() - timedelta(days=28)
        self.processed_tokens = set()
        
        self.stdout.write(f"📅 Freshness Filter: {self.cutoff_date.date()}")

        # --- HUNT TARGETS (Full Adobe + MarTech Stack) ---
        hunt_targets = [
            # Adobe Stack (High Priority)
            'Adobe Analytics', 'Adobe Target', 'Adobe Campaign', 
            'Adobe Journey Optimizer', 'AJO', 
            'Adobe Experience Platform', 'Adobe Experience Cloud',
            'Adobe Customer Journey Analytics',
            'Marketo', 

            # Marketing Automation
            'Salesforce Marketing Cloud', 'HubSpot', 'Braze',
            'Klaviyo', 'Iterable', 'Customer.io', 
            
            # CDP & Data
            'Tealium', 'mParticle', 'Real-Time CDP', 'Segment',
            'Customer Data Platform', 'CDP',
            
            # Analytics
            'Google Analytics 4', 'GA4', 'Mixpanel', 'Amplitude',
            
            # General Roles (High Priority)
            'MarTech', 'MarTech Architect', 'Marketing Operations', 'Marketing Technologist'
        ]

        # --- SMART QUERIES (Maximum Coverage) ---
        base_sites = [
            # Greenhouse (US & EU)
            'site:boards.greenhouse.io',
            'site:boards.eu.greenhouse.io',
            'site:job-boards.greenhouse.io',
            
            # Lever (US & EU)
            'site:jobs.lever.co',
            'site:jobs.eu.lever.co',
            
            # SmartRecruiters (Jobs & Careers subdomains)
            'site:jobs.smartrecruiters.com',
            'site:careers.smartrecruiters.com',
            
            # Modern Tech ATS
            'site:jobs.ashbyhq.com',         
            'site:apply.workable.com',       
            'site:recruitee.com',
            
            # "Powered By" Footprints (Catch custom domains)
            '"powered by greenhouse"',
            '"powered by lever"',
            '"powered by ashby"',
            '"powered by workable"'
        ]
        
        base_sites_str = " OR ".join(base_sites)

        for tool in hunt_targets:
            query = f'"{tool}" ({base_sites_str})'
            
            self.stdout.write(f"\n🔎 Hunting: {query[:60]}...")
            links = self.search_google(query)
            self.stdout.write(f"   Found {len(links)} links. Analyzing...")

            for link in links:
                try:
                    self.analyze_and_fetch(link)
                    time.sleep(0.5) 
                except Exception as e:
                    pass

        self.stdout.write(self.style.SUCCESS(f"\n✨ Done! Added {self.total_added} jobs."))

    # --- STEALTH HEADERS ---
    def get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9',
            'Accept-Language': 'en-US,en;q=0.9',
        }

    def search_google(self, query):
        params = { "engine": "google", "q": query, "api_key": self.serpapi_key, "num": 30, "gl": "us", "hl": "en", "tbs": "qdr:m" }
        try:
            resp = requests.get("https://serpapi.com/search", params=params, timeout=10)
            return [r.get("link") for r in resp.json().get("organic_results", [])]
        except: return []

    # --- THE BRAIN: ANALYZE URL (FIXED FOR ALL GREENHOUSE DOMAINS) ---
    def analyze_and_fetch(self, url):
        # 1. Greenhouse (ROBUST REGEX FIX)
        if "greenhouse.io" in url and "embed" not in url:
            # This regex looks for the token immediately after the last component of the domain.
            match = re.search(r'(?:greenhouse\.io|eu\.greenhouse\.io|job-boards\.greenhouse\.io)/([^/]+)', url)
            
            if match and match.group(1) not in BLACKLIST_TOKENS:
                self.fetch_greenhouse_api(match.group(1))
                return

        # 2. Lever
        elif "lever.co" in url:
            match = re.search(r'lever\.co/([^/]+)', url)
            if match:
                self.fetch_lever_api(match.group(1))
                return

        # 3. Ashby
        elif "ashbyhq.com" in url:
            match = re.search(r'jobs\.ashbyhq\.com/([^/]+)', url)
            if match:
                self.fetch_ashby_api(match.group(1))
                return

        # 4. Workable
        elif "workable.com" in url:
            match = re.search(r'apply\.workable\.com/([^/]+)', url) or re.search(r'([^.]+)\.workable\.com', url)
            if match:
                self.fetch_workable_api(match.group(1))
                return

        # 5. SmartRecruiters
        elif "smartrecruiters.com" in url:
            match = re.search(r'smartrecruiters\.com/([^/]+)', url)
            if match:
                self.fetch_smartrecruiters_api(match.group(1))
                return

        # 6. Recruitee
        elif "recruitee.com" in url:
            match = re.search(r'([^.]+)\.recruitee\.com', url)
            if match:
                self.fetch_recruitee_api(match.group(1))
                return
        
        # 7. Fallback (Skipping deep sniffing as direct ATS links are better)
        pass 

    # --- API WORKERS (Implemented core workers, others are placeholders for conciseness) ---

    def fetch_greenhouse_api(self, token, silent_fail=False):
        if token in self.processed_tokens or token in BLACKLIST_TOKENS: return False
        
        domains = ["boards-api.greenhouse.io", "job-boards.greenhouse.io", "boards-api.eu.greenhouse.io"]
        found_jobs = False
        
        for domain in domains:
            try:
                api_url = f"https://{domain}/v1/boards/{token}/jobs?content=true"
                resp = requests.get(api_url, headers=self.get_headers(), timeout=5)
                
                if resp.status_code == 200:
                    jobs = resp.json().get('jobs', [])
                    if jobs:
                        self.processed_tokens.add(token)
                        found_jobs = True
                        if not silent_fail:
                            self.stdout.write(f"      ⬇️  Greenhouse ({domain}): Found {len(jobs)} jobs for {token}...")
                        
                        for item in jobs:
                            if self.is_fresh(item.get('updated_at')):
                                job_data = {
                                    "title": item.get('title'), 
                                    "company": token.capitalize(), 
                                    "location": item.get('location', {}).get('name'), 
                                    "description": item.get('content'), 
                                    "apply_url": item.get('absolute_url'),
                                    "remote": "remote" in item.get('location', {}).get('name', '').lower(),
                                    "role_type": "full_time", # Default; AI will refine
                                    "source": "Greenhouse"
                                }
                                self.screen_and_upsert(job_data)
                        return True
            except: pass
        
        return found_jobs

    def fetch_lever_api(self, token):
        if token in self.processed_tokens: return
        self.processed_tokens.add(token)
        
        for base_url in ["https://api.lever.co/v0/postings/", "https://api.eu.lever.co/v0/postings/"]:
            try:
                api_url = f"{base_url}{token}?mode=json"
                resp = requests.get(api_url, headers=self.get_headers(), timeout=5)
                if resp.status_code == 200:
                    jobs = resp.json()
                    self.stdout.write(f"      ⬇️  Lever ({'EU' if 'eu' in base_url else 'US'}): Found {len(jobs)} jobs for {token}...")
                    
                    for item in jobs:
                        ts = item.get('createdAt')
                        if ts:
                            dt = datetime.fromtimestamp(ts/1000.0, tz=timezone.utc)
                            if dt < self.cutoff_date: continue
                        
                        location_str = item.get('categories', {}).get('location')
                        job_data = {
                            "title": item.get('text'), 
                            "company": token.capitalize(), 
                            "location": location_str, 
                            "description": item.get('description'), 
                            "apply_url": item.get('hostedUrl'), 
                            "remote": "remote" in location_str.lower() if location_str else False,
                            "role_type": "full_time", 
                            "source": "Lever"
                        }
                        self.screen_and_upsert(job_data)
                    return 
            except: pass

    # --- Other API Workers (Placeholders - MUST be implemented to use full potential) ---
    # These functions must be fully implemented to get jobs from these sources.
    # I am providing the skeleton so the code compiles and runs without crashes.
    def fetch_ashby_api(self, company_name): pass 
    def fetch_workable_api(self, subdomain): pass
    def fetch_smartrecruiters_api(self, company_id): pass
    def fetch_recruitee_api(self, company_name): pass
    
    # --- SCREENING AND UPSERT LOGIC (Consolidated and Finalized) ---

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
        location = job_data.get("location", "")
        description = job_data.get("description", "")
        apply_url = job_data.get("apply_url", "")
        source = job_data.get("source", "API")

        if Job.objects.filter(apply_url=apply_url).exists(): 
            return

        # --- STAGE 2: SCREENING (The Brain) ---
        analysis = self.screener.screen(
            title=title,
            company=company,
            location=location,
            description=description,
            apply_url=apply_url,
        )
        
        status = analysis.get("status", "pending")
        score = analysis.get("score", 50.0)
        reason = analysis.get("reason", "No reason provided.")
        signals = analysis.get("details", {}).get("signals", {})

        # --- STAGE 3: UPSERT (The Database) ---
        job, created = Job.objects.get_or_create(
            apply_url=apply_url,
            defaults={
                "title": title,
                "company": company,
                "location": location,
                "remote": job_data.get("remote", False),
                "description": description,
                "role_type": signals.get("role_type", job_data.get("role_type", "full_time")),
                "is_active": (status == "approved"), # Only activate if approved
            },
        )
        
        # Update screening status/details
        job.screening_status = status
        job.screening_score = score
        job.screening_reason = reason
        job.screening_details = analysis.get("details", {})
        job.screened_at = timezone.now()

        # Update tags and tool Many-to-Many field
        tools_list = signals.get("stack", [])
        job.tags = f"{source}, {signals.get('role_type', 'Operations')}, {', '.join(tools_list)}"
        
        job.save()

        # Update ManyToMany field after save
        if tools_list:
            job.tools.clear() 
            for tool_name in tools_list:
                normalized_name = self.screener._normalize(tool_name)
                tool_obj = self.tool_cache.get(normalized_name)
                if tool_obj:
                    job.tools.add(tool_obj)


        # --- VERBOSE LOGGING ---
        clean_title = (title[:35] + '..') if len(title) > 35 else title
        if status == "approved":
            self.total_added += 1
            self.stdout.write(self.style.SUCCESS(f"         ✅ {clean_title} [APPROVED, Score: {score:.1f}]"))
        elif status == "pending":
            self.stdout.write(self.style.WARNING(f"         ⚠️ {clean_title} [PENDING, Score: {score:.1f}, Reason: {reason}]"))
        else: # Rejected
            self.stdout.write(self.style.NOTICE(f"         ❌ {clean_title} [{reason}]"))
