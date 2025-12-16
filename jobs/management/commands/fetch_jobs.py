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

# 🚫 BLACKLIST (Ignore these generic tokens)
BLACKLIST_TOKENS = {'embed', 'api', 'test', 'demo', 'jobs', 'careers', 'board'}

class Command(BaseCommand):
    help = 'The Gold Standard Hunter: AI-Powered Edition with Multi-ATS Support'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting AI Job Hunt...")
        
        self.screener = MarTechScreener()
        self.total_added = 0
        self.serpapi_key = os.environ.get('SERPAPI_KEY')
        self.cutoff_date = timezone.now() - timedelta(days=28)
        self.processed_tokens = set()
        
        if not self.serpapi_key:
            self.stdout.write(self.style.ERROR("❌ Error: Missing SERPAPI_KEY."))
            return

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
            # Query Construction
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

    # --- THE BRAIN: ANALYZE URL ---
    def analyze_and_fetch(self, url):
        # 1. Greenhouse
        if "greenhouse.io" in url and "embed" not in url:
            match = re.search(r'greenhouse\.io/([^/]+)', url)
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
        
        # 7. Fallback to Sniffing/Guessing
        self.sniff_vanity_page(url)

    def sniff_vanity_page(self, url):
        try:
            session = requests.Session()
            session.headers.update(self.get_headers())
            resp = session.get(url, timeout=10)
            
            if resp.status_code == 200:
                html = resp.text
                
                # Sniff Greenhouse
                gh_match = re.search(r'greenhouse\.io/([^/"\'?]+)', html)
                if gh_match:
                    token = gh_match.group(1)
                    if token not in BLACKLIST_TOKENS:
                        self.fetch_greenhouse_api(token)
                        return
                
                # Sniff Lever
                lever_match = re.search(r'jobs\.lever\.co/([^/"\'?]+)', html)
                if lever_match:
                    self.fetch_lever_api(lever_match.group(1))
                    return

            self.guess_token(url)

        except Exception:
            self.guess_token(url)

    def guess_token(self, url):
        domain_match = re.search(r'https?://(www\.)?([^/.]+)', url)
        if not domain_match: return

        base_guess = domain_match.group(2)
        guesses = [base_guess, base_guess + "metrics", base_guess + "io", base_guess + "inc", base_guess + "data"]
        
        for guess in guesses:
            if guess in self.processed_tokens: continue
            success = self.fetch_greenhouse_api(guess, silent_fail=True)
            if success: return 

    # --- API WORKERS ---

    def fetch_greenhouse_api(self, token, silent_fail=False):
        if token in self.processed_tokens or token in BLACKLIST_TOKENS: return False
        
        # Expanded Domain List for Greenhouse
        domains = [
            "boards-api.greenhouse.io", 
            "job-boards.greenhouse.io", 
            "job-boards.eu.greenhouse.io",
            "boards-api.eu.greenhouse.io" # EU API Endpoint
        ]
        
        found_jobs = False
        for domain in domains:
            try:
                # Try fetching from this domain
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
                                self.process_job(
                                    title=item.get('title'), 
                                    company=token.capitalize(), 
                                    location=item.get('location', {}).get('name'), 
                                    description=item.get('content'), 
                                    apply_url=item.get('absolute_url'), 
                                    source="Greenhouse"
                                )
                        return True
            except: pass
        
        return found_jobs

    def fetch_lever_api(self, token):
        if token in self.processed_tokens: return
        self.processed_tokens.add(token)
        try:
            # Try Standard Lever
            api_url = f"https://api.lever.co/v0/postings/{token}?mode=json"
            resp = requests.get(api_url, headers=self.get_headers(), timeout=5)
            if resp.status_code == 200:
                jobs = resp.json()
                self.stdout.write(f"      ⬇️  Lever: Found {len(jobs)} jobs for {token}...")
                for item in jobs:
                    ts = item.get('createdAt')
                    if ts:
                        dt = datetime.fromtimestamp(ts/1000.0, tz=timezone.utc)
                        if dt < self.cutoff_date: continue
                    
                    self.process_job(
                        title=item.get('text'), 
                        company=token.capitalize(), 
                        location=item.get('categories', {}).get('location'), 
                        description=item.get('description'), 
                        apply_url=item.get('hostedUrl'), 
                        source="Lever"
                    )
                return

            # Try EU Lever (Fallback)
            api_url_eu = f"https://api.eu.lever.co/v0/postings/{token}?mode=json"
            resp = requests.get(api_url_eu, headers=self.get_headers(), timeout=5)
            if resp.status_code == 200:
                jobs = resp.json()
                self.stdout.write(f"      ⬇️  Lever (EU): Found {len(jobs)} jobs for {token}...")
                for item in jobs:
                    ts = item.get('createdAt')
                    if ts:
                        dt = datetime.fromtimestamp(ts/1000.0, tz=timezone.utc)
                        if dt < self.cutoff_date: continue
                    self.process_job(
                        title=item.get('text'), 
                        company=token.capitalize(), 
                        location=item.get('categories', {}).get('location'), 
                        description=item.get('description'), 
                        apply_url=item.get('hostedUrl'), 
                        source="Lever"
                    )

        except: pass

    def fetch_ashby_api(self, company_name):
        if company_name in self.processed_tokens: return
        self.processed_tokens.add(company_name)
        
        url = f"https://api.ashbyhq.com/posting-api/job-board/{company_name}"
        try:
            resp = requests.get(url, headers=self.get_headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                jobs = data.get('jobs', [])
                if jobs:
                    self.stdout.write(f"      ⬇️  Ashby: Found {len(jobs)} jobs for {company_name}...")
                    for item in jobs:
                        self.process_job(
                            title=item.get('title'),
                            company=company_name.capitalize(),
                            location=item.get('location'),
                            description=item.get('descriptionHtml') or item.get('jobUrl'),
                            apply_url=item.get('jobUrl'),
                            source="Ashby"
                        )
        except: pass

    def fetch_workable_api(self, subdomain):
        if subdomain in self.processed_tokens: return
        self.processed_tokens.add(subdomain)

        url = f"https://apply.workable.com/api/v1/widget/accounts/{subdomain}"
        try:
            resp = requests.get(url, headers=self.get_headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                jobs = data.get('jobs', [])
                if jobs:
                    self.stdout.write(f"      ⬇️  Workable: Found {len(jobs)} jobs for {subdomain}...")
                    for item in jobs:
                        self.process_job(
                            title=item.get('title'),
                            company=subdomain.capitalize(),
                            location=f"{item.get('city', '')}, {item.get('country', '')}",
                            description=item.get('description'),
                            apply_url=item.get('url'),
                            source="Workable"
                        )
        except: pass

    def fetch_smartrecruiters_api(self, company_id):
        if company_id in self.processed_tokens: return
        self.processed_tokens.add(company_id)

        url = f"https://api.smartrecruiters.com/v1/companies/{company_id}/postings"
        try:
            resp = requests.get(url, headers=self.get_headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                jobs = data.get('content', [])
                if jobs:
                    self.stdout.write(f"      ⬇️  SmartRecruiters: Found {len(jobs)} jobs for {company_id}...")
                    for item in jobs:
                        self.process_job(
                            title=item.get('name'),
                            company=item.get('company', {}).get('name') or company_id.capitalize(),
                            location=item.get('location', {}).get('city'),
                            description=f"See full description at {item.get('ref')}",
                            apply_url=item.get('ref'),
                            source="SmartRecruiters"
                        )
        except: pass

    def fetch_recruitee_api(self, company_name):
        if company_name in self.processed_tokens: return
        self.processed_tokens.add(company_name)

        url = f"https://{company_name}.recruitee.com/api/offers"
        try:
            resp = requests.get(url, headers=self.get_headers(), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                jobs = data.get('offers', [])
                if jobs:
                    self.stdout.write(f"      ⬇️  Recruitee: Found {len(jobs)} jobs for {company_name}...")
                    for item in jobs:
                        self.process_job(
                            title=item.get('title'),
                            company=item.get('company_name') or company_name.capitalize(),
                            location=item.get('location'),
                            description=item.get('description'),
                            apply_url=item.get('careers_url'),
                            source="Recruitee"
                        )
        except: pass

    # --- UTILS ---
    def is_fresh(self, date_str):
        if not date_str: return True
        try:
            dt = dateutil.parser.parse(date_str)
            if dt.tzinfo is None: dt = timezone.make_aware(dt)
            return dt >= self.cutoff_date
        except: return True

    def process_job(self, title, company, location, description, apply_url, source):
        if Job.objects.filter(apply_url=apply_url).exists(): return
        
        # PASS COMPANY NAME TO SCREENER
        analysis = self.screener.screen_job(title, description, company_name=company)
        
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
