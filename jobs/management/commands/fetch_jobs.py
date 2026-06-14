import time
import re
import logging
import dateutil.parser
import requests
import os
import json
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlparse, urlunparse
from typing import Any, Dict
from bs4 import BeautifulSoup
from openai import OpenAI
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings
from django.db.models import Q

from jobs.models import Job, Tool, Category
from jobs.screener import MarTechScreener
from jobs.tool_catalog import resolve_tool_name

logger = logging.getLogger("jobs.fetch")

class Command(BaseCommand):
    help = 'The "Direct-Apply" Hunter: Smart Deduplication + Geocoding + Clean URLs + Auto-Cleanup.'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting Job Hunt (Optimized Batch Mode)...")

        # --- 0. INIT GEOCODER ---
        self.geolocator = Nominatim(user_agent="martechstack_jobs_bot_v2")
        self.location_cache = {}

        # --- 1. AUTO-CLEANUP ---
        # Dead-link checking is handled by the dedicated check_dead_links command
        # (run_daily_tasks runs it right before this command).
        # Keep rejected jobs for 30 days so _is_duplicate still recognizes them
        # and we don't re-fetch + re-screen (paid AI calls) the same bad jobs daily.
        purge_cutoff = timezone.now() - timedelta(days=30)
        deleted_count = Job.objects.filter(screening_status='rejected', updated_at__lt=purge_cutoff).delete()[0]
        self.stdout.write(f"🧹 Database Cleanup: Removed {deleted_count} old rejected jobs (>30 days).")
        
        self.serpapi_key = os.environ.get('SERPAPI_KEY')
        self.serper_key = os.environ.get('SERPER_API_KEY')
        self.openai_key = os.environ.get('OPENAI_API_KEY')

        # Search provider switch: set SEARCH_PROVIDER=serper or serpapi to force one.
        # Default: use Serper if its key is set, otherwise fall back to SerpAPI.
        self.search_provider = os.environ.get('SEARCH_PROVIDER', '').strip().lower()
        if self.search_provider not in ('serper', 'serpapi'):
            self.search_provider = 'serper' if self.serper_key else 'serpapi'

        if self.search_provider == 'serper' and not self.serper_key:
            self.stdout.write(self.style.ERROR("❌ Error: SEARCH_PROVIDER=serper but SERPER_API_KEY is missing."))
            return
        if self.search_provider == 'serpapi' and not self.serpapi_key:
            self.stdout.write(self.style.ERROR("❌ Error: Missing SERPAPI_KEY."))
            return

        self.stdout.write(f"🔌 Search provider: {self.search_provider}")

        self.client = OpenAI(api_key=self.openai_key, timeout=30, max_retries=2) if self.openai_key else None
        self.screener = MarTechScreener()
        self.total_added = 0
        self.stats = defaultdict(int)  # per-source observability counters
        # Anti-flooding: cap how many roles from ONE company go live per run so
        # the board never shows a wall of 15 jobs from a single employer.
        self.company_counts = defaultdict(int)
        # Anti-flooding cap. Tuned for current low total volume: a single
        # martech-heavy company posting 5-8 relevant roles is signal, not flood,
        # so we keep them all live. Revisit downward once total live volume grows
        # large enough that one company could dominate the board.
        self.MAX_APPROVED_PER_COMPANY = 8

        self.tool_cache = {self.screener._normalize(t.name): t for t in Tool.objects.all()}
        # Default category for auto-created tools (valid stacks not yet in the DB).
        self.default_category, _ = Category.objects.get_or_create(
            name="MarTech", defaults={"slug": "martech"}
        )
        self.cutoff_date = timezone.now() - timedelta(days=14)
        self.processed_tokens = set()

        # ATS Groups (Domains to search)
        ats_groups = [
            "site:greenhouse.io OR site:lever.co OR site:ashbyhq.com OR site:jobs.smartrecruiters.com",
            "site:myworkdayjobs.com OR site:taleo.net OR site:icims.com OR site:jobvite.com",
            "site:bamboohr.com OR site:recruitee.com OR site:workable.com OR site:applytojob.com"
        ]

        # VENDOR EXCLUSION LIST (Prevents scraping the tool's own careers page if needed)
        vendor_domains = {
            "Braze": "braze.com",
            "Iterable": "iterable.com",
            "Customer.io": "customer.io",
            "Marketo": "adobe.com",
            "Adobe": "adobe.com",
            "Salesforce": "salesforce.com",
            "HubSpot": "hubspot.com",
            "Segment": "segment.com",
            "Tealium": "tealium.com",
            "Klaviyo": "klaviyo.com",
            "mParticle": "mparticle.com",
            "Amplitude": "amplitude.com",
            "Mixpanel": "mixpanel.com",
            "Optimizely": "optimizely.com"
        }

        # Load Targets
        target_lines = []
        target_file = os.path.join(settings.BASE_DIR, 'hunt_targets.txt')
        if os.path.exists(target_file):
            with open(target_file, 'r') as f:
                target_lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        if not target_lines:
            target_lines = ['MarTech']

        # --- MAIN LOOP ---
        for group_query in ats_groups:
            for line in target_lines:
                # 1. Parse the OR line
                parts = [p.strip() for p in line.split(' OR ')]
                
                intitle_parts = []
                exclude_str = ""
                
                for p in parts:
                    clean_p = p.replace('"', '') 
                    intitle_parts.append(f'intitle:"{clean_p}"')
                    
                    if clean_p in vendor_domains:
                        exclude_str += f" -site:{vendor_domains[clean_p]}"
                
                joined_intitle = " OR ".join(intitle_parts)
                final_query = f'({joined_intitle}) ({group_query}){exclude_str}'

                self.stdout.write(f"\n🔎 Hunting Batch: {parts[:3]}... (Last 14 Days)")
                time.sleep(1.0) # Respect rate limits
                
                links = self.search_google(final_query, num=100, tbs="qdr:d14")
                self.stdout.write(f"   Found {len(links)} links. Processing...")

                for link in links:
                    try:
                        self.analyze_and_fetch(link)
                        time.sleep(0.5)
                    except Exception as e:
                        self.stats["link:error"] += 1
                        logger.warning("Link processing failed for %s: %s", link, e)

        # --- PER-SOURCE RUN SUMMARY (observability) ---
        self.stdout.write(self.style.SUCCESS(f"\n✨ Done! Added {self.total_added} new jobs."))
        self.stdout.write("📊 Ingestion summary (source: outcome = count):")
        if self.stats:
            for key in sorted(self.stats):
                self.stdout.write(f"   {key} = {self.stats[key]}")
        else:
            self.stdout.write("   (no jobs seen — check sources/keys)")
        # Also log so it lands in the Render log aggregation, not just stdout.
        logger.info("fetch_jobs summary: added=%s stats=%s", self.total_added, dict(self.stats))

    def search_google(self, query, num=100, tbs="qdr:d14"):
        if self.search_provider == 'serper':
            return self._search_serper(query, num=num, tbs=tbs)
        return self._search_serpapi(query, num=num, tbs=tbs)

    def _search_serpapi(self, query, num=100, tbs="qdr:d14"):
        params = {
            "engine": "google",
            "q": query,
            "api_key": self.serpapi_key,
            "num": num,
            "gl": "us",
            "hl": "en",
            "tbs": tbs
        }
        try:
            resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
            if resp.status_code == 200:
                return [r.get("link") for r in resp.json().get("organic_results", [])]
        except: pass
        return []

    def _search_serper(self, query, num=100, tbs="qdr:d14"):
        # Serper.dev: same Google results, pay-as-you-go credits.
        # Note: Serper charges extra credits above 10 results, so we cap at 30
        # (3 credits) — top results carry nearly all the relevant postings.
        # Serper only accepts the standard Google ranges (qdr:h/d/w/m/y), not
        # custom spans like qdr:d14 — map those to the nearest standard range.
        if tbs and tbs.startswith("qdr:d") and tbs != "qdr:d":
            tbs = "qdr:w"
        payload = {
            "q": query,
            "num": min(num, 30),
            "gl": "us",
            "hl": "en",
        }
        if tbs:
            payload["tbs"] = tbs
        headers = {"X-API-KEY": self.serper_key, "Content-Type": "application/json"}
        try:
            resp = requests.post("https://google.serper.dev/search", json=payload, headers=headers, timeout=15)
            if resp.status_code == 200:
                return [r.get("link") for r in resp.json().get("organic", [])]
            else:
                self.stdout.write(self.style.WARNING(f"   ⚠️ Serper HTTP {resp.status_code}: {resp.text[:200]}"))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"   ⚠️ Serper request failed: {e}"))
        return []
    
    def _clean_url(self, url):
        """
        Aggressively removes 'apply' endpoints to ensure we scrape the description page.
        """
        if not url: return ""
        
        # 1. Remove hash fragments
        url = url.split('#')[0]
        
        # 2. Aggressively strip trailing /apply, /login, /autofill, /useMyLastApplication
        # Regex explanation:
        # /(apply|login|autofill|useMyLastApplication) -> look for these keywords starting with /
        # .*$ -> match EVERYTHING after them until the end of the string
        url = re.sub(r'/(apply|login|autofill|useMyLastApplication).*$', '', url, flags=re.IGNORECASE)
        
        # 3. Standard Parse rebuild to ensure valid structure
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, '', ''))

    def _is_duplicate(self, title, company, clean_url):
        if Job.objects.filter(apply_url=clean_url).exists():
            return True
        # Check against last 30 days to prevent duplicates with slight URL variations
        if Job.objects.filter(title__iexact=title, company__iexact=company, created_at__gte=timezone.now() - timedelta(days=30)).exists():
            return True
        return False

    def analyze_and_fetch(self, url):
        clean_url = self._clean_url(url)
        
        # Specialized Scrapers
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

        # Fallback AI Scraper for generic ATS (Workday, Taleo, etc.)
        if any(x in clean_url for x in ['myworkdayjobs.com', 'taleo.net', 'icims.com', 'jobvite.com', 'bamboohr.com']):
            # Ensure we are not scraping a search result page
            if any(k in clean_url for k in ['/job/', '/jobs/', '/detail/', '/req/', '/position/', '/career/']):
                 self.fetch_generic_ai(clean_url)
                 
    def get_headers(self):
        return {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

    # ... (API Fetchers for Greenhouse, Lever, etc. remain the same) ...
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
                            "description": item.get('content'), "apply_url": item.get('absolute_url'), 
                            "work_arrangement": arr, "source": "Greenhouse"
                        })
        except Exception as e:
            self.stats["Greenhouse:error"] += 1
            logger.warning("Greenhouse board '%s' failed: %s", token, e)

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
                        sr = item.get('salaryRange') or {}
                        salary = (f"{int(sr['min']):,} - {int(sr['max']):,} {sr.get('currency','')}".strip()
                                  if sr.get('min') and sr.get('max') else None)
                        self.screen_and_upsert({
                            "title": item.get('text'), "company": token.capitalize(), "location": clean_loc,
                            "description": item.get('description'), "apply_url": item.get('hostedUrl'),
                            "work_arrangement": arr, "source": "Lever", "salary": salary
                        })
        except Exception as e:
            self.stats["Lever:error"] += 1
            logger.warning("Lever board '%s' failed: %s", token, e)

    def fetch_ashby_api(self, company):
        if company in self.processed_tokens: return
        self.processed_tokens.add(company)
        try:
            resp = requests.post("https://api.ashbyhq.com/posting-api/job-board/" + company, headers=self.get_headers(), timeout=5)
            if resp.status_code == 200:
                for item in resp.json().get('jobs', []):
                    loc_obj = item.get('location') or {}
                    if isinstance(loc_obj, str): raw_loc = loc_obj
                    else: raw_loc = item.get('locationName') or "Remote"
                    clean_loc, arr = self._clean_location(raw_loc, item.get('isRemote', False))
                    self.screen_and_upsert({
                        "title": item.get('title'), "company": company.capitalize(), "location": clean_loc,
                        "description": f"Full details at {item.get('jobUrl')}", "apply_url": item.get('jobUrl'),
                        "work_arrangement": arr, "source": "Ashby", "salary": item.get('compensationTierSummary')
                    })
        except Exception as e:
            self.stats["Ashby:error"] += 1
            logger.warning("Ashby board '%s' failed: %s", company, e)

    def fetch_workable_api(self, sub):
        if sub in self.processed_tokens: return
        self.processed_tokens.add(sub)
        try:
            resp = requests.get(f"https://apply.workable.com/api/v1/widget/accounts/{sub}", headers=self.get_headers(), timeout=5)
            if resp.status_code == 200:
                for item in resp.json().get('jobs', []):
                    if self.is_fresh(item.get('published_on')):
                        parts = [item.get('city'), item.get('state'), item.get('country')]
                        raw_loc = ", ".join([p for p in parts if p])
                        clean_loc, arr = self._clean_location(raw_loc, item.get('telecommuting', False))
                        self.screen_and_upsert({
                            "title": item.get('title'), "company": sub.capitalize(), "location": clean_loc, 
                            "description": item.get('description'), "apply_url": item.get('url'), 
                            "work_arrangement": arr, "source": "Workable"
                        })
        except Exception as e:
            self.stats["Workable:error"] += 1
            logger.warning("Workable board '%s' failed: %s", sub, e)

    def fetch_smartrecruiters_api(self, company):
        if company in self.processed_tokens: return
        self.processed_tokens.add(company)
        try:
            resp = requests.get(f"https://api.smartrecruiters.com/v1/companies/{company}/postings", headers=self.get_headers(), timeout=5)
            if resp.status_code == 200:
                for item in resp.json().get('content', []):
                    if self.is_fresh(item.get('releasedDate')):
                        try:
                            d = requests.get(f"https://api.smartrecruiters.com/v1/companies/{company}/postings/{item.get('id')}", timeout=3).json()
                            desc = d.get('jobAd',{}).get('sections',{}).get('jobDescription',{}).get('text','')
                        except: desc = "See Job Post"
                        loc = item.get('location', {})
                        parts = [loc.get('city'), loc.get('region'), loc.get('country')]
                        raw_loc = ", ".join([p for p in parts if p])
                        clean_loc, arr = self._clean_location(raw_loc, loc.get('remote', False))
                        self.screen_and_upsert({
                            "title": item.get('name'), "company": company.capitalize(), "location": clean_loc,
                            "description": desc, "apply_url": f"https://jobs.smartrecruiters.com/{company}/{item.get('id')}", 
                            "work_arrangement": arr, "source": "SmartRecruiters"
                        })
        except Exception as e:
            self.stats["SmartRecruiters:error"] += 1
            logger.warning("SmartRecruiters board '%s' failed: %s", company, e)

    def fetch_generic_ai(self, url):
        if self._is_duplicate("", "", url): return 
        self.stdout.write(f"   🤖 AI Scraping: {url}...")
        try:
            resp = requests.get(url, headers=self.get_headers(), timeout=15, allow_redirects=True)
            if resp.status_code != 200 or "/search" in resp.url or "/jobs" == resp.url.split('/')[-1]: return
            soup = BeautifulSoup(resp.text, 'html.parser')
            for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript", "header"]): tag.extract()
            text = " ".join(soup.get_text(separator=' ').split())[:60000]
            if len(text) < 250: return
            
            prompt = f"Extract title, company, location (format: City, State, Country), is_remote, description_html (clean HTML) as JSON from: {text[:4000]}"
            completion = self.client.chat.completions.create(model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
            data = json.loads(completion.choices[0].message.content)
            clean_loc, arr = self._clean_location(data.get('location'), data.get('is_remote', False))
            self.screen_and_upsert({
                "title": data.get('title'), "company": data.get('company'), "location": clean_loc,
                "description": data.get('description_html') or data.get('description'), "apply_url": url, "work_arrangement": arr, "source": "AI Scraper"
            })
        except Exception as e:
            self.stdout.write(f"      ❌ AI Failed: {e}")

    def resolve_logo(self, company_name):
        if not company_name: return None
        return f"https://www.google.com/s2/favicons?domain={company_name.lower().replace(' ', '')}.com&sz=128"

    def is_fresh(self, date_str):
        # No date (common for some ATS APIs) -> keep, since these are curated
        # boards. But an UNPARSEABLE date means a format we don't understand --
        # fail closed so a source format change can't silently flood stale jobs.
        if not date_str: return True
        try:
            dt = dateutil.parser.parse(date_str)
            if dt.tzinfo is None: dt = timezone.make_aware(dt)
            return dt >= self.cutoff_date
        except Exception:
            return False
    
    def screen_and_upsert(self, job_data):
        source = job_data.get("source", "?")
        self.stats[f"{source}:seen"] += 1
        clean_url = self._clean_url(job_data.get("apply_url"))
        if self._is_duplicate(job_data.get("title"), job_data.get("company"), clean_url):
            self.stats[f"{source}:dupe"] += 1
            return
        analysis = self.screener.screen(job_data.get("title",""), job_data.get("company"), job_data.get("location"), job_data.get("description"), clean_url)
        score = float(analysis.get("score", 50.0))
        if score <= 0:
            self.stats[f"{source}:rejected"] += 1
            return

        status = analysis.get("status", "pending")
        # Anti-flooding: excess approved roles from the same company this run are
        # demoted to 'pending' (review queue) instead of flooding the live board.
        if status == "approved":
            ckey = (job_data.get("company") or "").strip().lower()
            if self.company_counts[ckey] >= self.MAX_APPROVED_PER_COMPANY:
                status = "pending"
                self.stats[f"{source}:capped"] += 1
            else:
                self.company_counts[ckey] += 1
        self.stats[f"{source}:{status}"] += 1
        signals = analysis.get("details", {}).get("signals", {})

        raw_function = signals.get("function", "other")
        valid_functions = {"engineering", "operations", "data", "other"}
        fn = raw_function if raw_function in valid_functions else "other"
        # role_type is employment type — the screener sometimes returns a
        # specialty (e.g. "MOPs") here, which is NOT a valid choice. Validate
        # against the real choices and default to full_time otherwise.
        valid_role_types = {"full_time", "contract", "part_time", "temporary", "internship"}
        raw_role = (signals.get("role_type") or "").strip().lower().replace("-", "_").replace(" ", "_")
        role_type = raw_role if raw_role in valid_role_types else "full_time"
        # Real salary from the ATS payload when available (never fabricated).
        salary = (job_data.get("salary") or "").strip() or None
        job = Job.objects.create(
            title=job_data.get("title"), company=job_data.get("company"), company_logo=self.resolve_logo(job_data.get("company")),
            location=job_data.get("location"), work_arrangement=job_data.get("work_arrangement"),
            description=job_data.get("description"), apply_url=clean_url,
            role_type=role_type, screening_status=status, salary_range=salary,
            screening_score=score, screening_reason=analysis.get("reason", ""),
            is_active=(status == "approved"), screened_at=timezone.now(), tags=f"{job_data.get('source')}",
            function=fn,
            screening_details=analysis.get("details", {}),
        )
        for raw in signals.get("stack", []):
            tool = self._resolve_tool(raw)
            if tool:
                job.tools.add(tool)
        if status == "approved":
            self.total_added += 1
            self.stdout.write(self.style.SUCCESS(f"   ✅ {job.title}"))

    def _resolve_tool(self, raw):
        """Normalize a raw stack name to a canonical Tool, auto-creating valid
        but missing ones. Unrecognized names are dropped (prevents junk tools)."""
        canon = resolve_tool_name(raw)
        if not canon:
            # Fall back to an exact existing-tool match before giving up.
            existing = self.tool_cache.get(self.screener._normalize(raw))
            return existing
        key = canon.lower()
        tool = self.tool_cache.get(key)
        if tool:
            return tool
        tool, created = Tool.objects.get_or_create(
            name=canon,
            defaults={"slug": slugify(canon), "category": self.default_category},
        )
        self.tool_cache[key] = tool
        if created:
            self.stats["tool:created"] += 1
            logger.info("Auto-created canonical tool: %s", canon)
        return tool

    def resolve_location_automatically(self, raw_loc):
        if not raw_loc or len(raw_loc) < 3: return raw_loc
        if raw_loc in self.location_cache: return self.location_cache[raw_loc]
        try:
            location = self.geolocator.geocode(raw_loc, language="en", addressdetails=True, timeout=10)
            if location:
                addr = location.raw.get('address', {})
                city = addr.get('city') or addr.get('town') or addr.get('village') or addr.get('county')
                state = addr.get('state') or addr.get('region')
                country = addr.get('country')
                parts = [p for p in [city, state, country] if p]
                formatted_loc = ", ".join(parts)
                self.location_cache[raw_loc] = formatted_loc
                return formatted_loc
        except: pass
        return raw_loc

    def _clean_location(self, location_str, is_remote_flag):
        if not location_str: return "Remote", 'remote'
        clean_loc = location_str.strip().replace(' | ', ', ').replace('/', ', ').replace('(', '').replace(')', '')
        clean_loc = re.sub(r'\s*,\s*', ', ', clean_loc)
        loc_lower = clean_loc.lower()
        arrangement = 'onsite'
        if is_remote_flag or any(k in loc_lower for k in {'remote', 'anywhere', 'wfh', 'work from home'}): 
            arrangement = 'remote'
        elif any(k in loc_lower for k in {'hybrid', 'flexible'}): 
            arrangement = 'hybrid'
        if arrangement != 'remote':
            clean_loc = self.resolve_location_automatically(clean_loc)
        return clean_loc, arrangement
