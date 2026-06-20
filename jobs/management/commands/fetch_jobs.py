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

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify
from django.conf import settings
from django.db import IntegrityError
from django.db.models import Q

from jobs.models import Job, Tool, Category, CompanySource, clean_html_description
from jobs.screener import MarTechScreener
from jobs.tool_catalog import resolve_tool_name

logger = logging.getLogger("jobs.fetch")

# Free-text country name -> ISO-2 code, for structured location capture.
_COUNTRY_CODES = {
    "united states": "US", "usa": "US", "u.s.": "US", "u.s.a.": "US",
    "united kingdom": "GB", "uk": "GB", "u.k.": "GB", "england": "GB",
    "scotland": "GB", "wales": "GB",
    "canada": "CA", "australia": "AU", "germany": "DE", "france": "FR",
    "netherlands": "NL", "ireland": "IE", "spain": "ES", "singapore": "SG",
    "mexico": "MX", "brazil": "BR", "india": "IN", "poland": "PL",
    "portugal": "PT", "italy": "IT", "sweden": "SE",
    # International expansion targets (Sprint: non-US traffic).
    "china": "CN", "hong kong": "HK",
    "united arab emirates": "AE", "uae": "AE", "u.a.e.": "AE",
    "dubai": "AE", "abu dhabi": "AE",
}

# SERP discovery country rotation (Google `gl` codes). Discovery seeds the
# CompanySource registry; once a board is learned, daily --sources-only polls
# it for free, so we only pay to DISCOVER each board once.
#
# US is the core market and is scanned EVERY day. Each day we add ONE rotating
# international market on top, sweeping the whole list over a rolling window.
# So the daily run is US + 1 country (2 passes); a manual `--countries all`
# run seeds every market at once.
_DISCOVERY_GL_PRIMARY = "us"
_DISCOVERY_GL_ROTATION = ["gb", "in", "sg", "de", "cn", "fr", "ca", "nl", "ae"]
_DISCOVERY_GL = [_DISCOVERY_GL_PRIMARY] + _DISCOVERY_GL_ROTATION

class Command(BaseCommand):
    help = 'The "Direct-Apply" Hunter: Smart Deduplication + Geocoding + Clean URLs + Auto-Cleanup.'

    # Auto-disable a CompanySource after this many consecutive empty direct polls.
    EMPTY_POLLS_BEFORE_DISABLE = 5

    def add_arguments(self, parser):
        parser.add_argument(
            "--sources-only", action="store_true",
            help="Skip SERP discovery; poll only the saved CompanySource registry (cheap daily run).",
        )
        parser.add_argument(
            "--no-discovery", action="store_true",
            help="Alias for --sources-only.",
        )
        parser.add_argument(
            "--countries", type=str, default="",
            help=(
                "Comma-separated Google gl codes to run SERP discovery for "
                "(e.g. 'us,gb,in'), or 'all' for every target market. "
                "Default: rotate one country per day (cost-neutral)."
            ),
        )

    def handle(self, *args, **options):
        self.sources_only = options.get("sources_only") or options.get("no_discovery")
        self.discovery_countries = self._resolve_discovery_countries(options.get("countries", ""))
        mode = "DIRECT POLL (registry only)" if self.sources_only else "SERP discovery + registry"
        self.stdout.write(f"🚀 Starting Job Hunt — mode: {mode}...")
        if not self.sources_only:
            self.stdout.write(f"🌍 Discovery countries (gl): {', '.join(self.discovery_countries)}")

        # --- 0. INIT ---
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

        # Search keys are only required for SERP discovery. A --sources-only run
        # polls the saved registry directly and needs no search provider.
        if not self.sources_only:
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

        # In-memory dedup caches — avoids 3 DB queries per candidate job.
        self._known_ids = set(Job.objects.values_list("external_id", flat=True).exclude(external_id=""))
        self._known_urls = set(Job.objects.values_list("apply_url", flat=True).exclude(apply_url=""))

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

        # --- PHASE 1: DIRECT POLL of the learned CompanySource registry ---
        # Cheap, complete coverage of boards we already know employ MarTech roles.
        # Runs in every mode (it costs no search spend), and is the ONLY phase in
        # --sources-only mode.
        self.poll_company_sources()

        # --- PHASE 2: SERP DISCOVERY (skipped in --sources-only mode) ---
        # Finds NEW boards we don't know about yet; each success is recorded into
        # the registry so future direct polls pick it up.
        if not self.sources_only:
            for gl in self.discovery_countries:
                self.stdout.write(f"\n🌍 ===== Discovery pass for country: {gl.upper()} =====")
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

                        self.stdout.write(f"\n🔎 [{gl.upper()}] Hunting Batch: {parts[:3]}... (Last 14 Days)")
                        time.sleep(1.0) # Respect rate limits

                        links = self.search_google(final_query, num=100, tbs="qdr:d14", gl=gl)
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
        # Bust the salary-guide cache so the next page load reflects new salary data.
        from django.core.cache import cache as django_cache
        django_cache.delete('salary_guide_data_v2')

    def _resolve_discovery_countries(self, raw):
        """Decide which Google `gl` codes this run discovers against.

        Priority: explicit --countries arg > DISCOVERY_COUNTRIES env > daily
        rotation. 'all' expands to the full target list. The default scans the
        US (core market) EVERY day plus ONE rotating international market, so
        the US is never starved while every other market is swept over a
        rolling window — and the registry makes that coverage cumulative.
        """
        raw = (raw or "").strip() or os.environ.get("DISCOVERY_COUNTRIES", "").strip()
        if raw.lower() == "all":
            return list(_DISCOVERY_GL)
        if raw:
            picked = [c.strip().lower() for c in raw.split(",") if c.strip()]
            return picked or [_DISCOVERY_GL_PRIMARY]
        # Default: US every day + one rotating international market.
        idx = datetime.utcnow().date().toordinal() % len(_DISCOVERY_GL_ROTATION)
        return [_DISCOVERY_GL_PRIMARY, _DISCOVERY_GL_ROTATION[idx]]

    def search_google(self, query, num=100, tbs="qdr:d14", gl="us"):
        if self.search_provider == 'serper':
            return self._search_serper(query, num=num, tbs=tbs, gl=gl)
        return self._search_serpapi(query, num=num, tbs=tbs, gl=gl)

    def _search_serpapi(self, query, num=100, tbs="qdr:d14", gl="us"):
        params = {
            "engine": "google",
            "q": query,
            "api_key": self.serpapi_key,
            "num": num,
            "gl": gl,
            "hl": "en",
            "tbs": tbs
        }
        try:
            resp = requests.get("https://serpapi.com/search", params=params, timeout=15)
            if resp.status_code == 200:
                return [r.get("link") for r in resp.json().get("organic_results", [])]
        except requests.RequestException as e:
            logger.warning("SerpAPI request failed: %s", e)
        return []

    def _search_serper(self, query, num=100, tbs="qdr:d14", gl="us"):
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
            "gl": gl,
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
        
        # 2. Strip trailing /apply, /login, /autofill, /useMyLastApplication —
        # but only as WHOLE path segments. The keyword must be followed by a "/"
        # or the end of the string, so a real job slug like
        # ".../senior-marketing-applylytics-engineer" is NOT truncated.
        url = re.sub(r'/(apply|login|autofill|useMyLastApplication)(?=/|$).*$', '', url, flags=re.IGNORECASE)
        
        # 3. Standard Parse rebuild to ensure valid structure
        parsed = urlparse(url)
        return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, '', ''))

    def _is_duplicate(self, title, company, clean_url, external_id=""):
        # Check in-memory caches first (no DB queries for the common case).
        if external_id and external_id in self._known_ids:
            return True
        if clean_url and clean_url in self._known_urls:
            return True
        # Fall back to DB only for title/company fuzzy match (can't cache this).
        if title and company and Job.objects.filter(
            title__iexact=title, company__iexact=company,
            created_at__gte=timezone.now() - timedelta(days=30)
        ).exists():
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
        elif "recruitee.com" in clean_url:
            match = re.search(r'([^.]+)\.recruitee\.com', clean_url)
            if match: self.fetch_recruitee_api(match.group(1)); return
        elif "myworkdayjobs.com" in clean_url:
            # Real Workday CXS API fetcher (replaces the old AI-scraper fallback).
            self.fetch_workday_api(clean_url); return

        # Fallback AI Scraper for other generic ATS (Taleo, iCIMS, etc.)
        if any(x in clean_url for x in ['taleo.net', 'icims.com', 'jobvite.com', 'bamboohr.com']):
            # Ensure we are not scraping a search result page
            if any(k in clean_url for k in ['/job/', '/jobs/', '/detail/', '/req/', '/position/', '/career/']):
                 self.fetch_generic_ai(clean_url)
                 
    def get_headers(self):
        return {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}

    # --- Sprint 3b: structured location + source registry ---------------------
    def _geo_fields(self, clean_loc, arrangement):
        """Derive (country ISO-2, region, remote_scope) from a cleaned location.

        remote_scope: "" if not remote, a country code if the remote role is
        geo-restricted, else "anywhere".
        """
        low = (clean_loc or "").lower()
        country = ""
        for name, code in _COUNTRY_CODES.items():
            if name in low:
                country = code
                break
        # ", CA" style US state suffix implies the US even without "United States".
        if not country and re.search(r',\s*[a-z]{2}$', low):
            country = "US"
        parts = [p.strip() for p in (clean_loc or "").split(",") if p.strip()]
        region = parts[1] if len(parts) >= 2 and parts[1].lower() not in _COUNTRY_CODES else ""
        remote_scope = ""
        if arrangement == "remote":
            remote_scope = country or "anywhere"
        return country, region, remote_scope

    def record_source(self, ats_type, token, name="", board_url=""):
        """Auto-learn: remember a board that fetched successfully so future
        `--sources-only` runs can poll it directly (no search spend)."""
        if not token and not board_url:
            return
        try:
            obj, created = CompanySource.objects.get_or_create(
                ats_type=ats_type, token=token or board_url[:200],
                defaults={"name": name or (token or "").capitalize(), "board_url": board_url},
            )
            if created:
                self.stats["source:learned"] += 1
            elif board_url and obj.board_url != board_url:
                obj.board_url = board_url
                obj.save(update_fields=["board_url"])
        except Exception as e:
            logger.warning("record_source failed (%s:%s): %s", ats_type, token, e)

    def poll_company_sources(self):
        """Phase 1: poll every enabled board in the registry directly."""
        from django.db.models import F
        # Never-polled boards (last_polled_at IS NULL) go first, then oldest poll.
        sources = list(
            CompanySource.objects.filter(enabled=True).order_by(F("last_polled_at").asc(nulls_first=True))
        )
        if not sources:
            self.stdout.write("📇 Registry empty — nothing to direct-poll yet (SERP discovery will seed it).")
            return
        self.stdout.write(f"📇 Direct-polling {len(sources)} saved company sources...")
        dispatch = {
            "greenhouse": lambda s: self.fetch_greenhouse_api(s.token),
            "lever": lambda s: self.fetch_lever_api(s.token),
            "ashby": lambda s: self.fetch_ashby_api(s.token),
            "workable": lambda s: self.fetch_workable_api(s.token),
            "smartrecruiters": lambda s: self.fetch_smartrecruiters_api(s.token),
            "recruitee": lambda s: self.fetch_recruitee_api(s.token),
            "workday": lambda s: self.fetch_workday_api(s.board_url or s.token),
        }
        self._polling_registry = True
        total = len(sources)
        for idx, s in enumerate(sources, 1):
            fn = dispatch.get(s.ats_type)
            if not fn:
                continue
            self._poll_seen = 0
            before = self.total_added
            try:
                fn(s)
            except Exception as e:
                logger.warning("Direct poll failed for %s: %s", s, e)
            added = self.total_added - before
            # Progress line so a long --sources-only run is visibly alive.
            self.stdout.write(f"   [{idx}/{total}] {s.ats_type}:{s.token or s.name} → +{added}")
            s.last_polled_at = timezone.now()
            s.last_seen_count = self._poll_seen
            s.last_added_count = added
            if self._poll_seen == 0:
                s.consecutive_empty += 1
                if s.consecutive_empty >= self.EMPTY_POLLS_BEFORE_DISABLE:
                    s.enabled = False
                    self.stats["source:auto_disabled"] += 1
                    self.stdout.write(self.style.WARNING(
                        f"   ⚠ Auto-disabled '{s.name}' ({s.ats_type}) after "
                        f"{s.consecutive_empty} empty polls."))
            else:
                s.consecutive_empty = 0
            s.save(update_fields=["last_polled_at", "last_seen_count", "last_added_count", "consecutive_empty", "enabled"])
            time.sleep(0.3)
        self._polling_registry = False

    # ... (API Fetchers for Greenhouse, Lever, etc. remain the same) ...
    def fetch_greenhouse_api(self, token):
        if token in self.processed_tokens: return
        self.processed_tokens.add(token)
        try:
            resp = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true", headers=self.get_headers(), timeout=5)
            if resp.status_code == 200:
                self.record_source("greenhouse", token, token.capitalize())
                for item in resp.json().get('jobs', []):
                    if self.is_fresh(item.get('updated_at')):
                        raw_loc = item.get('location', {}).get('name')
                        clean_loc, arr = self._clean_location(raw_loc, "remote" in (raw_loc or "").lower())
                        self.screen_and_upsert({
                            "title": item.get('title'), "company": token.capitalize(), "location": clean_loc,
                            "description": item.get('content'), "apply_url": item.get('absolute_url'),
                            "work_arrangement": arr, "source": "Greenhouse",
                            "external_id": f"greenhouse:{item.get('id')}",
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
                self.record_source("lever", token, token.capitalize())
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
                            "work_arrangement": arr, "source": "Lever", "salary": salary,
                            "external_id": f"lever:{item.get('id')}",
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
                self.record_source("ashby", company, company.capitalize())
                cutoff = timezone.now() - timedelta(days=14)
                for item in resp.json().get('jobs', []):
                    published = item.get('publishedAt') or item.get('updatedAt') or ''
                    if published:
                        try:
                            if dateutil.parser.parse(published).replace(tzinfo=None) < cutoff.replace(tzinfo=None):
                                continue
                        except Exception:
                            pass
                    loc_obj = item.get('location') or {}
                    if isinstance(loc_obj, str): raw_loc = loc_obj
                    else: raw_loc = item.get('locationName') or "Remote"
                    clean_loc, arr = self._clean_location(raw_loc, item.get('isRemote', False))
                    # Ashby's job-board API returns the real JD; use it instead of
                    # a placeholder so detail pages and Google for Jobs schema have
                    # genuine content.
                    raw_desc = item.get('descriptionHtml') or item.get('descriptionPlain') or ''
                    description = clean_html_description(raw_desc) if raw_desc else f"Full details at {item.get('jobUrl')}"
                    self.screen_and_upsert({
                        "title": item.get('title'), "company": company.capitalize(), "location": clean_loc,
                        "description": description, "apply_url": item.get('jobUrl'),
                        "work_arrangement": arr, "source": "Ashby", "salary": item.get('compensationTierSummary'),
                        "external_id": f"ashby:{item.get('id')}",
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
                self.record_source("workable", sub, sub.capitalize())
                for item in resp.json().get('jobs', []):
                    if self.is_fresh(item.get('published_on')):
                        parts = [item.get('city'), item.get('state'), item.get('country')]
                        raw_loc = ", ".join([p for p in parts if p])
                        clean_loc, arr = self._clean_location(raw_loc, item.get('telecommuting', False))
                        self.screen_and_upsert({
                            "title": item.get('title'), "company": sub.capitalize(), "location": clean_loc,
                            "description": item.get('description'), "apply_url": item.get('url'),
                            "work_arrangement": arr, "source": "Workable",
                            "external_id": f"workable:{item.get('id') or item.get('shortcode')}",
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
                self.record_source("smartrecruiters", company, company.capitalize())
                for item in resp.json().get('content', []):
                    if self.is_fresh(item.get('releasedDate')):
                        try:
                            d = requests.get(f"https://api.smartrecruiters.com/v1/companies/{company}/postings/{item.get('id')}", timeout=5).json()
                            desc = (d.get('jobAd') or {}).get('sections', {}).get('jobDescription', {}).get('text', '')
                        except Exception:
                            desc = "See Job Post"
                        loc = item.get('location', {})
                        parts = [loc.get('city'), loc.get('region'), loc.get('country')]
                        raw_loc = ", ".join([p for p in parts if p])
                        clean_loc, arr = self._clean_location(raw_loc, loc.get('remote', False))
                        self.screen_and_upsert({
                            "title": item.get('name'), "company": company.capitalize(), "location": clean_loc,
                            "description": desc, "apply_url": f"https://jobs.smartrecruiters.com/{company}/{item.get('id')}",
                            "work_arrangement": arr, "source": "SmartRecruiters",
                            "external_id": f"smartrecruiters:{item.get('id')}",
                        })
        except Exception as e:
            self.stats["SmartRecruiters:error"] += 1
            logger.warning("SmartRecruiters board '%s' failed: %s", company, e)

    def fetch_recruitee_api(self, company):
        if company in self.processed_tokens: return
        self.processed_tokens.add(company)
        try:
            resp = requests.get(f"https://{company}.recruitee.com/api/offers/", headers=self.get_headers(), timeout=5)
            if resp.status_code == 200:
                self.record_source("recruitee", company, company.capitalize())
                for item in resp.json().get('offers', []):
                    if self.is_fresh(item.get('published_at') or item.get('created_at')):
                        parts = [item.get('city'), item.get('state_name') or item.get('state_code'), item.get('country')]
                        raw_loc = ", ".join([p for p in parts if p]) or item.get('location')
                        is_remote = bool(item.get('remote')) or "remote" in (raw_loc or "").lower()
                        clean_loc, arr = self._clean_location(raw_loc, is_remote)
                        self.screen_and_upsert({
                            "title": item.get('title'), "company": company.capitalize(), "location": clean_loc,
                            "description": item.get('description'), "apply_url": item.get('careers_url') or item.get('url'),
                            "work_arrangement": arr, "source": "Recruitee",
                            "external_id": f"recruitee:{item.get('id')}",
                        })
        except Exception as e:
            self.stats["Recruitee:error"] += 1
            logger.warning("Recruitee board '%s' failed: %s", company, e)

    def _workday_fresh(self, posted_on):
        """Workday `postedOn` is relative text ("Posted 5 Days Ago", "Posted
        30+ Days Ago", "Posted Today"). Return True if within the 14-day window.
        Unknown/missing format -> keep (fail-open) so a wording change can't
        silently drop a whole board."""
        if not posted_on:
            return True
        t = posted_on.lower()
        if "today" in t or "yesterday" in t or "hour" in t or "minute" in t:
            return True
        if "month" in t or "year" in t:
            return False
        m = re.search(r'(\d+)\+?\s*day', t)
        if m:
            return int(m.group(1)) <= 14
        return True

    def fetch_workday_api(self, board_url):
        """Workday CXS API. board_url is a full careers URL like
        https://<tenant>.<host>.myworkdayjobs.com/<lang?>/<site> — we derive the
        tenant/host/site and POST to the public /wday/cxs jobs endpoint.
        Paginates (Workday returns 20/page) and gates on postedOn freshness."""
        if board_url in self.processed_tokens: return
        self.processed_tokens.add(board_url)
        m = re.match(r'https?://([^.]+)\.([^.]+)\.myworkdayjobs\.com/(?:([a-z]{2}-[A-Z]{2})/)?([^/?#]+)', board_url)
        if not m:
            self.stats["Workday:skip_badurl"] += 1
            return
        tenant, host, _lang, site = m.group(1), m.group(2), m.group(3), m.group(4)
        api = f"https://{tenant}.{host}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
        base = f"https://{tenant}.{host}.myworkdayjobs.com/{('%s/' % _lang) if _lang else ''}{site}"
        PAGE = 20
        MAX_PAGES = 10  # cap coverage at 200 postings/board to bound cost
        try:
            recorded = False
            for page in range(MAX_PAGES):
                offset = page * PAGE
                resp = requests.post(api, json={"appliedFacets": {}, "limit": PAGE, "offset": offset, "searchText": ""},
                                     headers={**self.get_headers(), "Content-Type": "application/json"}, timeout=8)
                if resp.status_code != 200:
                    self.stats["Workday:error"] += 1
                    return
                payload = resp.json()
                postings = payload.get('jobPostings', [])
                if not postings:
                    break
                if not recorded:
                    self.record_source("workday", f"{tenant}/{site}", tenant.capitalize(), board_url=board_url)
                    recorded = True
                for item in postings:
                    if not self._workday_fresh(item.get('postedOn')):
                        self.stats["Workday:stale"] += 1
                        continue
                    ext_path = item.get('externalPath') or ""
                    _bullet0 = ((item.get('bulletFields') or []) + [None])[0]
                    raw_loc = str(item.get('locationsText') or _bullet0 or "")
                    is_remote = "remote" in raw_loc.lower()
                    clean_loc, arr = self._clean_location(raw_loc, is_remote)
                    self.screen_and_upsert({
                        "title": item.get('title'), "company": tenant.capitalize(), "location": clean_loc,
                        "description": item.get('title'), "apply_url": f"{base}{ext_path}",
                        "work_arrangement": arr, "source": "Workday",
                        "external_id": f"workday:{ext_path}",
                    })
                # Stop once we've walked the whole board.
                if offset + PAGE >= payload.get('total', 0):
                    break
                time.sleep(0.3)
        except Exception as e:
            self.stats["Workday:error"] += 1
            logger.warning("Workday board '%s' failed: %s", board_url, e)

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
        # Track postings seen during a direct registry poll so we can auto-disable
        # boards that return nothing (vs. boards that just yield no NEW jobs).
        if getattr(self, "_polling_registry", False):
            self._poll_seen += 1
        clean_url = self._clean_url(job_data.get("apply_url"))
        external_id = (job_data.get("external_id") or "").strip()
        if self._is_duplicate(job_data.get("title"), job_data.get("company"), clean_url, external_id):
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
        # Structured location captured at ingest (Sprint 3b).
        country, region, remote_scope = self._geo_fields(job_data.get("location"), job_data.get("work_arrangement"))
        try:
            job = Job.objects.create(
                title=job_data.get("title"), company=job_data.get("company"), company_logo=self.resolve_logo(job_data.get("company")),
                location=job_data.get("location"), work_arrangement=job_data.get("work_arrangement"),
                description=job_data.get("description"), apply_url=clean_url,
                role_type=role_type, screening_status=status, salary_range=salary,
                screening_score=score, screening_reason=analysis.get("reason", ""),
                is_active=(status == "approved"), screened_at=timezone.now(), tags=f"{job_data.get('source')}",
                function=fn,
                screening_details=analysis.get("details", {}),
                external_id=external_id,
                country=country, region=region, remote_scope=remote_scope,
            )
        except IntegrityError:
            self.stats[f"{source}:dupe"] += 1
            return
        # Keep in-memory caches current so later candidates in this run see it.
        if external_id:
            self._known_ids.add(external_id)
        if clean_url:
            self._known_urls.add(clean_url)
        for raw in signals.get("stack", []):
            tool = self._resolve_tool(raw)
            if tool:
                job.tools.add(tool)
        if status == "approved":
            self.total_added += 1
            self.stdout.write(self.style.SUCCESS(f"   ✅ {job.title}"))

    def _resolve_tool(self, raw):
        """Normalize a raw stack name to a canonical Tool, auto-creating valid
        but missing ones. Unrecognized names are dropped entirely — we never
        attach a job to a non-canonical tool, so junk tool pages can't be kept
        alive (or re-created) through ingestion."""
        canon = resolve_tool_name(raw)
        if not canon:
            return None
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
        # Nominatim removed — ATS APIs already provide clean location strings
        # and live geocoding calls block the entire cron run for 30+ minutes.
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
