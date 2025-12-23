import time
import re
import dateutil.parser 
import requests
import os
import json
from datetime import datetime, timedelta
from typing import Any, Dict
from bs4 import BeautifulSoup
from openai import OpenAI

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from jobs.models import Job, Tool
from jobs.screener import MarTechScreener

class Command(BaseCommand):
    help = 'The "Direct-Apply" Hunter: Finds jobs ONLY on official global ATS portals (EU/US/APAC).'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting Global Direct-Apply Job Hunt...")
        
        # 1. Setup
        self.serpapi_key = os.environ.get('SERPAPI_KEY')
        self.openai_key = os.environ.get('OPENAI_API_KEY')
        
        if not self.serpapi_key:
            self.stdout.write(self.style.ERROR("❌ Error: Missing SERPAPI_KEY."))
            return

        self.client = OpenAI(api_key=self.openai_key) if self.openai_key else None
        self.screener = MarTechScreener()
        self.total_added = 0
        self.tool_cache = {self.screener._normalize(t.name): t for t in Tool.objects.all()}
        self.cutoff_date = timezone.now() - timedelta(days=28)
        self.processed_tokens = set()

        # 2. The "Global ATS" List
        # Note: "site:greenhouse.io" automatically covers "eu.greenhouse.io"
        # "site:myworkdayjobs.com" covers "wd3.myworkdayjobs.com" (EU data centers)
        ats_groups = [
            # Group A: Modern Tech (Global)
            "site:greenhouse.io OR site:lever.co OR site:ashbyhq.com OR site:jobs.smartrecruiters.com",
            # Group B: Enterprise Giants (Global)
            "site:myworkdayjobs.com OR site:taleo.net OR site:icims.com OR site:jobvite.com",
            # Group C: Mid-Market
            "site:bamboohr.com OR site:recruitee.com OR site:workable.com OR site:applytojob.com"
        ]

        # 3. Load Targets
        hunt_targets = ['Marketing Operations', 'MarTech', 'Salesforce Marketing Cloud', 'HubSpot', 'Marketo']

        # 4. Execute Search
        for group_query in ats_groups:
            for keyword in hunt_targets:
                query = f'"{keyword}" ({group_query})'
                self.stdout.write(f"\n🔎 Hunting: {keyword} in {group_query[:30]}...")
                
                # Fetch 50 results per keyword
                links = self.search_google(query, num=50)
                self.stdout.write(f"   Found {len(links)} direct links. Processing...")

                for link in links:
                    try:
                        self.analyze_and_fetch(link)
                        time.sleep(0.5) 
                    except Exception:
                        pass

        self.stdout.write(self.style.SUCCESS(f"\n✨ Done! Added {self.total_added} Direct-Apply jobs."))

    # --- SERPAPI ENGINE ---
    def search_google(self, query, num=50):
        params = { 
            "engine": "google", "q": query, "api_key": self.serpapi_key, 
            "num": num, "gl": "us", "hl": "en", "tbs": "qdr:m"
        }
        try:
            resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
            if resp.status_code == 200:
                results = resp.json().get("organic_results", [])
                return [r.get("link") for r in results]
        except: pass
        return []

    # --- THE BRAIN: ANALYZE URL (Region Aware) ---
    def analyze_and_fetch(self, url):
        # 1. Greenhouse (US & EU)
        # Matches: boards.greenhouse.io, eu.greenhouse.io, etc.
        if "greenhouse.io" in url:
            match = re.search(r'(?:greenhouse\.io|eu\.greenhouse\.io|job-boards\.greenhouse\.io)/([^/]+)', url)
            if match: self.fetch_greenhouse_api(match.group(1)); return
            
        # 2. Lever (Global)
        elif "lever.co" in url:
            match = re.search(r'lever\.co/([^/]+)', url)
            if match: self.fetch_lever_api(match.group(1)); return
            
        # 3. Ashby (Global)
        elif "ashbyhq.com" in url:
            match = re.search(r'jobs\.ashbyhq\.com/([^/]+)', url)
            if match: self.fetch_ashby_api(match.group(1)); return
            
        # 4. Workable (Global)
        elif "workable.com" in url:
            match = re.search(r'apply\.workable\.com/([^/]+)', url) or re.search(r'([^.]+)\.workable\.com', url)
            if match: self.fetch_workable_api(match.group(1)); return
            
        # 5. SmartRecruiters (Global)
        elif "smartrecruiters.com" in url:
            match = re.search(r'jobs\.smartrecruiters\.com/([^/]+)', url) or re.search(r'([^.]+)\.smartrecruiters\.com', url)
            if match: self.fetch_smartrecruiters_api(match.group(1)); return

        # 6. Enterprise Fallback (Workday, Taleo, iCIMS - All Regions)
        # Matches wd3.myworkdayjobs.com (Europe), wd1... (US), etc.
        if any(x in url for x in ['myworkdayjobs.com', 'taleo.net', 'icims.com', 'jobvite.com', 'bamboohr.com']):
            if any(k in url for k in ['/job/', '/jobs/', '/detail/', '/req/', '/position/', '/career/']):
                 self.fetch_generic_ai(url)

    # --- SPECIFIC API WORKERS ---
    def get_headers(self):
        return {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

    def fetch_greenhouse_api(self, token):
        if token in self.processed_tokens: return
        self.processed_tokens.add(token)
        # Note: The API endpoint is the same for US/EU content usually, 
        # but if needed we could check 'eu.greenhouse.io' in the future.
        try:
            resp = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true", headers=self.get_headers(), timeout=5)
            if resp.status_code == 200:
                for item in resp.json().get('jobs', []):
                    if self.is_fresh(item.get('updated_at')):
                        raw_loc = item.get('location', {}).get('name')
                        clean_loc, arr = self._clean_location(raw_loc, "remote" in (raw_loc or "").lower())
                        self.screen_and_upsert({"title": item.get('title'), "company": token.capitalize(), "location": clean_loc, "description": item.get('content'), "apply_url": item.get('absolute_url'), "work_arrangement": arr, "source": "Greenhouse"})
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
                        clean_loc, arr = self._clean_location(raw_loc, "remote" in (raw_loc or "").lower())
                        self.screen_and_upsert({"title": item.get('text'), "company": token.capitalize(), "location": clean_loc, "description": item.get('description'), "apply_url": item.get('hostedUrl'), "work_arrangement": arr, "source": "Lever"})
        except: pass

    def fetch_ashby_api(self, company):
        if company in self.processed_tokens: return
        self.processed_tokens.add(company)
        try:
            resp = requests.post("https://api.ashbyhq.com/posting-api/job-board/" + company, headers=self.get_headers(), timeout=5)
            if resp.status_code == 200:
                for item in resp.json().get('jobs', []):
                    clean_loc, arr = self._clean_location(item.get('location'), item.get('isRemote', False))
                    self.screen_and_upsert({"title": item.get('title'), "company": company.capitalize(), "location": clean_loc, "description": f"See {item.get('jobUrl')}", "apply_url": item.get('jobUrl'), "work_arrangement": arr, "source": "Ashby"})
        except: pass

    def fetch_workable_api(self, sub):
        if sub in self.processed_tokens: return
        self.processed_tokens.add(sub)
        try:
            resp = requests.get(f"https://apply.workable.com/api/v1/widget/accounts/{sub}", headers=self.get_headers(), timeout=5)
            if resp.status_code == 200:
                for item in resp.json().get('jobs', []):
                    if self.is_fresh(item.get('published_on')):
                        clean_loc, arr = self._clean_location(f"{item.get('city')}, {item.get('country')}", item.get('telecommuting', False))
                        self.screen_and_upsert({"title": item.get('title'), "company": sub.capitalize(), "location": clean_loc, "description": item.get('description'), "apply_url": item.get('url'), "work_arrangement": arr, "source": "Workable"})
        except: pass

    def fetch_smartrecruiters_api(self, company):
        if company in self.processed_tokens: return
        self.processed_tokens.add(company)
        try:
            resp = requests.get(f"https://api.smartrecruiters.com/v1/companies/{company}/postings", headers=self.get_headers(), timeout=5)
            if resp.status_code == 200:
                for item in resp.json().get('content', []):
                    if self.is_fresh(item.get('releasedDate')):
                        raw_loc = item.get('location', {}).get('city')
                        clean_loc, arr = self._clean_location(raw_loc, item.get('location', {}).get('remote', False))
                        self.screen_and_upsert({
                            "title": item.get('name'), "company": company.capitalize(), "location": clean_loc,
                            "description": "See Job Post", "apply_url": f"https://jobs.smartrecruiters.com/{company}/{item.get('id')}", 
                            "work_arrangement": arr, "source": "SmartRecruiters"
                        })
        except: pass

    # --- GENERIC AI FALLBACK (Global Support) ---
    def fetch_generic_ai(self, url):
        if Job.objects.filter(apply_url=url).exists(): return
        
        self.stdout.write(f"   🤖 AI Scraping: {url}...")
        try:
            resp = requests.get(url, headers=self.get_headers(), timeout=10)
            if resp.status_code != 200: return
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            for tag in soup(["script", "style", "nav", "footer", "iframe"]): tag.extract()
            text = " ".join(soup.get_text().split())[:5000]

            prompt = f"""Extract job details into JSON. URL: {url}
            Text: {text}
            Fields: title, company, location, description_summary, is_remote (bool).
            Output JSON only."""

            completion = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            data = json.loads(completion.choices[0].message.content)
            
            clean_loc, arr = self._clean_location(data.get('location'), data.get('is_remote', False))
            self.screen_and_upsert({
                "title": data.get('title'), "company": data.get('company'), "location": clean_loc,
                "description": data.get('description_summary'), "apply_url": url,
                "work_arrangement": arr, "source": "AI Scraper"
            })
        except Exception as e:
            self.stdout.write(f"      ❌ AI Failed: {e}")

    # --- HELPERS ---
    def resolve_logo(self, company_name):
        if not company_name: return None
        clean = company_name.lower().replace(' ', '').replace(',', '')
        return f"https://www.google.com/s2/favicons?domain={clean}.com&sz=128"

    def is_fresh(self, date_str):
        if not date_str: return True
        try:
            dt = dateutil.parser.parse(date_str)
            if dt.tzinfo is None: dt = timezone.make_aware(dt)
            return dt >= self.cutoff_date
        except: return True
    
    def screen_and_upsert(self, job_data: Dict[str, Any]):
        title = job_data.get("title", "")
        if Job.objects.filter(apply_url=job_data.get("apply_url")).exists(): return

        analysis = self.screener.screen(
            title=title, company=job_data.get("company"), location=job_data.get("location"),
            description=job_data.get("description"), apply_url=job_data.get("apply_url")
        )
        
        status = analysis.get("status", "pending")
        signals = analysis.get("details", {}).get("signals", {})

        job = Job.objects.create(
            title=title, company=job_data.get("company"), company_logo=self.resolve_logo(job_data.get("company")),
            location=job_data.get("location"), work_arrangement=job_data.get("work_arrangement"),
            description=job_data.get("description"), apply_url=job_data.get("apply_url"),
            role_type=signals.get("role_type", "full_time"), screening_status=status,
            screening_score=analysis.get("score", 50.0), screening_reason=analysis.get("reason", ""),
            is_active=(status == "approved"), screened_at=timezone.now(),
            tags=f"{job_data.get('source')}"
        )
        
        for tool_name in signals.get("stack", []):
            t_obj = self.tool_cache.get(self.screener._normalize(tool_name))
            if t_obj: job.tools.add(t_obj)

        if status == "approved":
            self.total_added += 1
            self.stdout.write(self.style.SUCCESS(f"   ✅ {title[:30]}.. [APPROVED]"))

    def _clean_location(self, location_str, is_remote_flag):
        if not location_str: return "On-site", 'onsite'
        clean_loc = location_str.strip().replace(' | ', ', ').replace('/', ', ').replace('(', '').replace(')', '')
        loc_lower = clean_loc.lower()
        arrangement = 'onsite'
        if is_remote_flag or any(k in loc_lower for k in {'remote', 'anywhere', 'wfh'}): arrangement = 'remote'
        if any(k in loc_lower for k in {'hybrid', 'flexible'}): arrangement = 'hybrid'
        
        all_work_keywords = {'remote', 'hybrid', 'onsite', 'flexible', 'wfh', 'anywhere'}
        location_parts = [p.strip() for p in clean_loc.split(',') if p.strip() and not any(k in p.strip().lower() for k in all_work_keywords)]
        final_location = ", ".join(location_parts)
        return (final_location or arrangement.capitalize()), arrangement
