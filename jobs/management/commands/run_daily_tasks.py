from django.core.management.base import BaseCommand
from django.core.management import call_command
import time

class Command(BaseCommand):
    help = 'MASTER COMMAND: Runs all daily maintenance, ingestion, and content tasks in order.'

    def _run(self, label, command_name):
        # Isolate each step so one failure doesn't abort the whole daily run.
        self.stdout.write(label)
        try:
            call_command(command_name)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Step '{command_name}' failed: {e}"))

    def handle(self, *args, **options):
        self.stdout.write("🚀 STARTING DAILY AUTOPILOT SEQUENCE...")

        # 1. CLEANUP (Clear the deck)
        self._run("\n[1/5] 🧹 Checking for Dead Links & Expired Roles...", 'check_dead_links')
        self._run("      ⏳ Expiring featured/pinned...", 'expire_featured')
        self._run("      🗑️ Cleaning stale jobs...", 'clean_stale_jobs')

        # 2. INGESTION (Get new jobs)
        self._run("\n[2/5] 🏹 Hunting via API (Deep Search)...", 'fetch_jobs')

        # 3. POLISH (Images)
        self._run("\n[3/5] 🎨 Backfilling Logos...", 'update_logos')

        # 4. CONTENT ENGINE (Automated Blog)
        self._run("\n[4/5] ✍️ Running AI Blog Engine...", 'generate_blog')

        # 5. INDEXING (Ping Google)
        # This forces Google to crawl the new jobs and the new blog post.
        self._run("\n[5/5] 📡 Pinging Google Indexing API...", 'index_jobs')

        self.stdout.write(self.style.SUCCESS("\n✨ AUTOPILOT COMPLETE. System is fresh."))
