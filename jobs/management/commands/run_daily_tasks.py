from django.core.management.base import BaseCommand
from django.core.management import call_command
import time

class Command(BaseCommand):
    help = 'MASTER COMMAND: Runs all daily maintenance, ingestion, and content tasks in order.'

    def handle(self, *args, **options):
        self.stdout.write("🚀 STARTING DAILY AUTOPILOT SEQUENCE...")

        # 1. CLEANUP (Clear the deck)
        self.stdout.write("\n[1/5] 🧹 Checking for Dead Links & Expired Roles...")
        call_command('check_dead_links')   
        call_command('expire_featured')    
        call_command('clean_stale_jobs')   

        # 2. INGESTION (Get new jobs)
        self.stdout.write("\n[2/5] 🏹 Hunting via API (Deep Search)...")
        call_command('fetch_jobs')

        # 3. POLISH (Images)
        self.stdout.write("\n[3/5] 🎨 Backfilling Logos...")
        call_command('update_logos')
        
        # 4. CONTENT ENGINE (Automated Blog)
        self.stdout.write("\n[4/5] ✍️ Running AI Blog Engine...")
        call_command('generate_blog')
        
        # 5. INDEXING (Ping Google)
        # This forces Google to crawl the new jobs and the new blog post.
        self.stdout.write("\n[5/5] 📡 Pinging Google Indexing API...")
        try:
            call_command('index_jobs')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Indexing Failed: {e}"))
        
        self.stdout.write(self.style.SUCCESS("\n✨ AUTOPILOT COMPLETE. System is fresh."))
