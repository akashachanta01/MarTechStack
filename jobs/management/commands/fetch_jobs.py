import time
import re
import dateutil.parser 
import requests
import os
import json
from datetime import datetime, timedelta
from urllib.parse import urlparse, urlunparse
from typing import Any, Dict
from bs4 import BeautifulSoup
from openai import OpenAI

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.db.models import Q

from jobs.models import Job, Tool
from jobs.screener import MarTechScreener

class Command(BaseCommand):
    help = 'The "Direct-Apply" Hunter: Smart Deduplication + Clean URLs.'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting Job Hunt (Smart Deduplication Mode)...")
        
        self.serpapi_key = os.environ.get('SERPAPI_KEY')
        self.openai_key = os.environ.get('OPENAI_API_KEY')
        
        if not self.serpapi_key:
            self.stdout.write(self.style.ERROR("❌ Error: Missing SERPAPI_KEY."))
            return

        self.client = OpenAI(api_key=self.openai_key) if self.openai_key else None
        self.screener = MarTechScreener()
        self.total_added = 0
        
        # Cache tools for fast tagging
        self.tool_cache = {self.screener._normalize(t.name): t for t in Tool.objects.all()}
        self.cutoff_date = timezone.now() - timedelta(days=28)
        self.processed_tokens = set()

        ats_groups = [
            "site:greenhouse.io OR site:lever.co OR site:ashbyhq.com OR site:jobs.smartrecruiters.com",
            "site:myworkdayjobs.com OR site:taleo.net OR site:icims.com OR site:jobvite.com",
            "site:bamboohr.com OR site:recruitee.com OR site:workable.com OR site:applytojob.com"
        ]

        hunt_targets = []
        target_file = os.path.join(settings.BASE_DIR, 'hunt_targets.txt')
        if os.path.exists(target_file):
            with open(target_file, 'r') as f:
                hunt_targets = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        if not hunt_targets:
            hunt_targets = ['MarTech']

        for group_query in ats_groups:
            for keyword in hunt_targets:
                # 1. INTITLE IS ON (High Quality)
                query = f'intitle:"{keyword}" ({group_query})'
                
                self.stdout.write(f"\n🔎 Hunting: {keyword}...")
                time.sleep(1.0)
                
                links = self.search_google(query, num=50)
                self.stdout.write(f"   Found {len(links)} links. Processing...")

                for link in links:
                    try:
                        self.analyze_and_fetch(link)
                        time.sleep(0.5) 
                    except Exception:
                        pass

        self.stdout.write(self.style.SUCCESS(f"\n✨ Done! Added {self.total_added} new jobs."))

    def search_google(self, query, num=50):
        # Removed date filter (qdr:m) so we find the hits, then let API check freshness
        params = { "engine": "google", "q": query, "api_key": self.serpapi_key, "num": num, "gl": "us", "hl": "en" }
        try:
            resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
            if resp.status_code == 200:
                return [r.get("link") for r in resp.json().get("organic_results", [])]
        except: pass
        return []

    def _clean_url(self, url):
        """Removes tracking parameters (utm_source, gh_src) to prevent duplicates"""
        if not url: return ""
        parsed = urlparse(url)
        # Reconstruct URL without query parameters (params after ?)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, '', ''))

    def _is_duplicate(self, title, company, clean_url):
        """Checks if job exists by URL OR by Title+Company combo"""
        # 1. URL Check
        if Job.objects.filter(apply_url=clean_url).exists():
            return True
        
        # 2. Title + Company Check (Fuzzy Duplicate Protection)
        # Prevents "Solution Expert" appearing 3 times even if URLs are different
        if Job.objects.filter(
            title__iexact=title, 
            company__iexact=company, 
            created_at__gte=timezone.now() - timedelta(days=30)
        ).exists():
            return True
            
        return False

    def analyze_and_fetch(self, url):
        # Clean the URL first so we don't process "greenhouse.io?source=linkedin" as new
        clean_url = self._clean_url(url)
        
        if "greenhouse.io" in clean_url:
            match = re.search(r'(?:greenhouse\.io|eu\.greenhouse\.io|job-boards\.greenhouse\.io)/([^/]+)', clean_url)
            if match: self.fetch_greenhouse_api(match.group(1)); return
        elif "lever.co" in clean_url:
            match = re.search(r'lever\.co/([^/]+)', clean_url)
            if match: self.fetch_lever_api(match.group(1)); return
        elif "ashbyhq.com" in clean_url:
            match = re.search(r'jobs\.ashbyhq\.com/([^/]+)', clean_url)
            if match: self.fetch_ashby_api(match.group(1)); return
        elif "workable.com" in clean_url:
            match = re.search(r'apply\.workable\.com/([^/]+)', clean_url) or re.search(r'([^.]+)\.workable\.com', clean_url)
            if match: self.fetch_workable_api(match.group(1)); return
        elif "smartrecruiters.com" in clean_url:
            match = re.search(r'jobs\.smartrecruiters\.com/([^/]+)', clean_url) or re.search(r'([^.]+)\.smartrecruiters\.com', clean_url)
            if match: self.fetch_smartrecruiters_api(match.group(1)); return

        if any(x in clean_url for x in ['myworkdayjobs.com', 'taleo.net', 'icims.com', 'jobvite.com', 'bamboohr.com']):
            if any(k in clean_url for k in ['/job/', '/jobs/', '/detail/', '/req/', '/position/', '/career/']):
                 self.fetch_generic_ai(clean_url)

    def get_headers(self):
        return {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

    def fetch_greenhouse_api(self, token):
        if token in self.processed_tokens: return
        self.processed_tokens.add(token)
        try:
            resp = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true", headers=self.get_headers(), timeout=5)
            if resp.status_code == 200:
                for item in resp.json().get('jobs', []):
                    if self.is_fresh(item.get('updated_at')):
                        raw_loc = item.get('location', {}).get('name')
                        clean_loc, arr = self._clean_location(raw_loc, "remote" in (raw_loc or "").lower())
                        self.screen_and_upsert({
                            "title": item.get('title'), "company": token.capitalize(), "location": clean_loc, 
                            "description": item.get('content'), "apply_url": item.get('absolute_url'), "work_arrangement": arr, "source": "Greenhouse"
