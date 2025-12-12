from django.core.management.base import BaseCommand
import feedparser
from jobs.models import Job
import time

class Command(BaseCommand):
    help = 'Fetches remote marketing jobs from WeWorkRemotely RSS'

    def handle(self, *args, **options):
        # We Work Remotely - Marketing Category RSS
        rss_url = "https://weworkremotely.com/categories/remote-marketing-jobs.rss"
        
        self.stdout.write(f"📡 Connecting to {rss_url}...")
        feed = feedparser.parse(rss_url)
        
        self.stdout.write(f"✅ Found {len(feed.entries)} entries.")
        
        count = 0
        for entry in feed.entries:
            # 1. Check if job already exists (by matching the link)
            if Job.objects.filter(apply_url=entry.link).exists():
                continue

            # 2. Extract Data
            # Note: WWR puts the company name in 'author' usually
            company_name = entry.get('author', 'Unknown Company')
            
            # 3. Create the Job
            Job.objects.create(
                title=entry.title,
                company=company_name,
                location="Remote", # It's a remote board
                description=entry.summary, # RSS provides HTML summary
                apply_url=entry.link,
                tags="Remote, Marketing",
                is_active=True # Auto-publish because WWR is trusted
            )
            count += 1
            
        self.stdout.write(self.style.SUCCESS(f"🚀 Imported {count} new jobs from RSS!"))
