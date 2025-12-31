from django.core.management.base import BaseCommand
from django.core.management import call_command
import time

class Command(BaseCommand):
    help = 'MASTER COMMAND: Runs all daily maintenance and ingestion tasks in order.'

    def handle(self, *args, **options):
        self.stdout.write("🚀 STARTING DAILY AUTOPILOT SEQUENCE...")

        # 1. CLEANUP (Clear the deck)
        self.stdout.write("\n[1/5] 🧹 Checking for Dead Links & Expired Roles...")
        call_command('check_dead_links')   # <--- The New Janitor
        call_command('expire_featured')    # Downgrades featured status
        call_command('clean_stale_jobs')   # Moves 60+ day old jobs to pending

        # 2. INGESTION (Get new jobs)
        # Run RSS first (Cheap & Fast)
        #self.stdout.write("\n[2/5] 📡 Fetching RSS Feeds...")
        #call_command('fetch_rss')
        
        # Run Hunter (Deep Search - Costs API Credits)
        self.stdout.write("\n[3/5] 🏹 Hunting via API (Deep Search)...")
        call_command('fetch_jobs')

        # 3. POLISH (Images)
        # Find logos for any new companies found above
        self.stdout.write("\n[4/5] 🎨 Backfilling Logos...")
        call_command('update_logos')
        
        self.stdout.write(self.style.SUCCESS("\n✨ AUTOPILOT COMPLETE. System is fresh."))
