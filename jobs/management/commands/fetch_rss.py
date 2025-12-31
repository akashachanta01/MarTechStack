import feedparser
import time
import re
import requests
import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from geopy.geocoders import Nominatim
from jobs.models import Job, Tool
from jobs.screener import MarTechScreener

class Command(BaseCommand):
    help = 'Fetches high-quality MarTech jobs from RSS Feeds with Geocoding & Smart Parsing'

    def handle(self, *args, **options):
        self.stdout.write("📡 Starting Smart RSS Import...")
        
        # 1. SETUP
        self.screener = MarTechScreener()
        self.tool_cache = {self.screener._normalize(t.name): t for t in Tool.objects.all()}
        self.geolocator = Nominatim(user_agent="martechstack_rss_bot_v1")
        self.location_cache = {}
        self.total_added = 0

        # 2. FEED LIST
        feeds = [
            {
                "name": "WeWorkRemotely",
                "url": "https://weworkremotely.com/categories/remote-marketing-jobs.rss",
                "tag": "WWR"
            },
            {
                "name": "Remotive",
                "url": "https://remotive.com/remote-jobs/marketing/feed",
                "tag": "Remotive"
            },
            {
                "name": "RemoteOK",
                "url": "https://remoteok.com/remote-marketing-jobs.rss",
                "tag": "RemoteOK"
            }
        ]

        for feed_config in feeds:
            self.process_feed(feed_config)

        self.stdout.write(self.style.SUCCESS(f"\n✨ RSS Import Complete! Added {self.total_added} new jobs."))

    def process_feed(self, config):
        self.stdout.write(f"\n🔌 Connecting to {config['name']}...")
        try:
            feed = feedparser.parse(config['url'])
            self.stdout.write(f"   Found {len(feed.entries)} entries. Analyzing...")

            for entry in feed.entries:
                self.process_entry(entry, config['tag'])
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Failed: {e}"))

    def process_entry(self, entry, source_tag):
        link = entry.get('link', '')
        if Job.objects.filter(apply_url=link).exists(): return

        # --- 1. SMART DATA EXTRACTION ---
        title_raw = entry.get('title', 'Unknown Role')
        author_raw = entry.get('author', '') or entry.get('company', '')
        
        # A. Extract Company & Title
        company, title = self.extract_company_and_title(title_raw, author_raw)
        
        # B. Extract Location (The Hard Part)
        raw_loc = self.extract_location_from_rss(entry, title_raw)
        
        # C. Geocode Location
        # Assume remote for RSS feeds unless specified otherwise
        clean_loc, arr = self._clean_location(raw_loc, is_remote_flag=True)

        # --- 2. LOGO RESOLUTION ---
        logo_url = None
        if company and company != "Unknown Company":
            domain_guess = company.lower().replace(' ', '').replace(',', '').replace('.', '')
            logo_url = f"https://www.google.com/s2/favicons?domain={domain_guess}.com&sz=128"

        # --- 3. SCREENING ---
        description = entry.get('summary', '') or entry.get('description', '')
        
        analysis = self.screener.screen(
            title=title, company=company, location=clean_loc, 
            description=description, apply_url=link
        )

        status = analysis.get("status", "pending")
        if status == "rejected": return

        # --- 4. SAVE ---
        signals = analysis.get("details", {}).get("signals", {})
        
        job = Job.objects.create(
            title=title,
            company=company,
            company_logo=logo_url,
            location=clean_loc,
            work_arrangement=arr,
            description=description,
            apply_url=link,
            role_type="full_time",
            screening_status=status,
            screening_score=analysis.get("score", 50.0),
            screening_reason=analysis.get("reason", "RSS Import"),
            is_active=(status == "approved"),
            tags=f"RSS, {source_tag}",
            screened_at=timezone.now()
        )

        for tool_name in signals.get("stack", []):
            t_obj = self.tool_cache.get(self.screener._normalize(tool_name))
            if t_obj: job.tools.add(t_obj)

        if status == "approved":
            self.total_added += 1
            self.stdout.write(self.style.SUCCESS(f"   ✅ {title[:30]}.. at {company}"))

    def extract_company_and_title(self, title_str, author_str):
        """
        Splits 'Role at Company' or 'Company: Role' patterns.
        """
        company = author_str
        title = title_str

        # Pattern 1: "Role at Company" (Common in WWR)
        if ' at ' in title and not company:
            parts = title.split(' at ')
            if len(parts) > 1:
                company = parts[-1].strip()
                title = " at ".join(parts[:-1]).strip()
        
        # Pattern 2: "Company: Role"
        if ':' in title and not company:
            parts = title.split(':')
            company = parts[0].strip()
            title = ":".join(parts[1:]).strip()
            
        # Clean up the company name
        company = self.clean_company_name(company)
        if not company: company = "Unknown Company"
        
        return company, title

    def clean_company_name(self, name):
        if not name: return ""
        # Remove common noise
        name = re.sub(r'( is hiring| is looking for| careers| jobs).*', '', name, flags=re.IGNORECASE)
        return name.strip()

    def extract_location_from_rss(self, entry, title):
        """
        Tries to find location in tags or title.
        """
        # 1. Check specific RSS tags (Remotive uses 'region', others use 'location')
        if 'region' in entry: return entry.region
        if 'location' in entry: return entry.location
        if 'job_listing_location' in entry: return entry.job_listing_location
        
        # 2. Check Title for (Location) or [Location]
        # Example: "Marketing Manager (London, UK)"
        match = re.search(r'\((.*?)\)$', title)
        if match:
            possible_loc = match.group(1)
            # Filter out non-locations like "Full Time"
            if len(possible_loc) > 3 and "Time" not in possible_loc:
                return possible_loc
                
        return "Remote"

    def resolve_location_automatically(self, raw_loc):
        """
        Geocoding Logic (Shared with API Hunter)
        """
        if not raw_loc or len(raw_loc) < 3: return raw_loc
        if raw_loc in self.location_cache: return self.location_cache[raw_loc]
        
        try:
            location = self.geolocator.geocode(raw_loc, language="en", addressdetails=True, timeout=5)
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
        
        # Automatic Resolution if we have a specific city name
        if arrangement == 'remote' and clean_loc.lower() != "remote":
             # Even if remote, if they said "Remote (London)", we want to standardize "London"
             clean_loc = self.resolve_location_automatically(clean_loc)
        elif arrangement != 'remote':
             clean_loc = self.resolve_location_automatically(clean_loc)

        return clean_loc, arrangement
