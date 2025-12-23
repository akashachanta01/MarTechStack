import feedparser
import time
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from jobs.models import Job, Tool
from jobs.screener import MarTechScreener

class Command(BaseCommand):
    help = 'Fetches high-quality MarTech jobs from RSS Feeds (WWR, Remotive, etc.)'

    def handle(self, *args, **options):
        self.stdout.write("📡 Starting RSS Feed Import...")
        
        # 1. Initialize Screener & Tools
        self.screener = MarTechScreener()
        self.tool_cache = {self.screener._normalize(t.name): t for t in Tool.objects.all()}
        self.total_added = 0

        # 2. Define Sources
        feeds = [
            {
                "name": "WeWorkRemotely (Marketing)",
                "url": "https://weworkremotely.com/categories/remote-marketing-jobs.rss",
                "source_tag": "WWR"
            },
            {
                "name": "Remotive (Marketing)",
                "url": "https://remotive.com/remote-jobs/marketing/feed",
                "source_tag": "Remotive"
            },
            {
                "name": "RemoteOK (Marketing)",
                "url": "https://remoteok.com/remote-marketing-jobs.rss",
                "source_tag": "RemoteOK"
            }
        ]

        for feed_config in feeds:
            self.process_feed(feed_config)

        self.stdout.write(self.style.SUCCESS(f"\n✨ RSS Import Complete! Added {self.total_added} new jobs."))

    def process_feed(self, config):
        self.stdout.write(f"\n🔌 Connecting to {config['name']}...")
        try:
            feed = feedparser.parse(config['url'])
            self.stdout.write(f"   Found {len(feed.entries)} entries. Screening...")

            for entry in feed.entries:
                try:
                    self.process_entry(entry, config['source_tag'])
                except Exception as e:
                    pass
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"   ❌ Failed to parse feed: {e}"))

    def process_entry(self, entry, source_tag):
        # 1. Deduplication
        link = entry.get('link', '')
        if Job.objects.filter(apply_url=link).exists():
            return

        # 2. Normalize Data
        title = entry.get('title', 'Unknown Role')
        company = entry.get('author', 'Unknown Company')
        # Some feeds put company in title like "Company: Role"
        if ':' in title and company == 'Unknown Company':
            parts = title.split(':')
            company = parts[0].strip()
            title = ':'.join(parts[1:]).strip()

        description = entry.get('summary', '') or entry.get('description', '')
        
        # 3. SCREEN IT (The most important part!)
        # We send it to your AI brain to decide if it's MarTech or just generic Marketing
        analysis = self.screener.screen(
            title=title, 
            company=company, 
            location="Remote", 
            description=description, 
            apply_url=link
        )

        status = analysis.get("status", "pending")
        
        # We only save if it's Approved or Pending (Skip Rejected)
        if status == "rejected":
            return

        # 4. Save Job
        signals = analysis.get("details", {}).get("signals", {})
        
        job = Job.objects.create(
            title=title,
            company=company,
            location="Remote",
            work_arrangement="remote",
            description=description,
            apply_url=link,
            role_type="full_time",
            screening_status=status,
            screening_score=analysis.get("score", 50.0),
            screening_reason=analysis.get("reason", "Imported from RSS"),
            is_active=(status == "approved"), # Auto-live if AI loves it
            tags=f"RSS, {source_tag}",
            screened_at=timezone.now()
        )

        # 5. Tag Tools
        for tool_name in signals.get("stack", []):
            t_obj = self.tool_cache.get(self.screener._normalize(tool_name))
            if t_obj: job.tools.add(t_obj)

        if status == "approved":
            self.total_added += 1
            self.stdout.write(self.style.SUCCESS(f"   ✅ {title[:40]}... [APPROVED]"))
        else:
            self.stdout.write(self.style.WARNING(f"   ⚠️ {title[:40]}... [PENDING]"))
