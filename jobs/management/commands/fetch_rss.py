import feedparser
import time
from django.core.management.base import BaseCommand
from django.utils import timezone
from jobs.models import Job, Tool
from jobs.screener import MarTechScreener

class Command(BaseCommand):
    help = 'Fetches high-quality MarTech jobs from RSS Feeds with Smart Company Detection'

    def handle(self, *args, **options):
        self.stdout.write("📡 Starting Smart RSS Import...")
        
        self.screener = MarTechScreener()
        self.tool_cache = {self.screener._normalize(t.name): t for t in Tool.objects.all()}
        self.total_added = 0

        # Hardcoded MVP Feed List
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

        # --- 1. SMART COMPANY EXTRACTION ---
        title_raw = entry.get('title', 'Unknown Role')
        company = entry.get('author', '').strip()
        
        # Heuristic A: "Role at Company" (Common in Remotive)
        if not company and ' at ' in title_raw:
            parts = title_raw.split(' at ')
            # Take the last part as company if it looks reasonable
            if len(parts) > 1:
                company = parts[-1].strip()
                title_raw = " at ".join(parts[:-1]).strip()

        # Heuristic B: "Company: Role" (Common in WWR)
        if not company and ':' in title_raw:
            parts = title_raw.split(':')
            company = parts[0].strip()
            title_raw = ":".join(parts[1:]).strip()
            
        # Fallback
        if not company: company = "Unknown Company"

        # --- 2. LOGO RESOLUTION ---
        logo_url = None
        if company != "Unknown Company":
            # Clean name for logo search (e.g. "Google Inc." -> "google")
            clean_name = company.lower().replace(' ', '').replace(',', '').replace('.', '')
            logo_url = f"https://www.google.com/s2/favicons?domain={clean_name}.com&sz=128"

        # --- 3. SCREENING ---
        description = entry.get('summary', '') or entry.get('description', '')
        
        analysis = self.screener.screen(
            title=title_raw, company=company, location="Remote", 
            description=description, apply_url=link
        )

        status = analysis.get("status", "pending")
        if status == "rejected": return

        # --- 4. SAVE ---
        signals = analysis.get("details", {}).get("signals", {})
        
        job = Job.objects.create(
            title=title_raw,
            company=company,
            company_logo=logo_url,  # <--- Now saving the logo!
            location="Remote",
            work_arrangement="remote",
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
            self.stdout.write(self.style.SUCCESS(f"   ✅ {title_raw[:30]}.. at {company} [APPROVED]"))
