import signal

from django.core.management.base import BaseCommand
from django.core.management import call_command


class StepTimeout(Exception):
    pass


class Command(BaseCommand):
    help = 'MASTER COMMAND: Runs all daily maintenance, ingestion, and content tasks in order.'

    # Per-step hard ceilings (seconds). A step that blows its budget is killed
    # and the run continues with the next step, so one hung external API can
    # never freeze the whole daily run again.
    TIMEOUTS = {
        'check_dead_links': 20 * 60,
        'expire_featured': 2 * 60,
        'clean_stale_jobs': 2 * 60,
        'fetch_jobs': 25 * 60,
        'update_logos': 10 * 60,
        'send_daily_digest': 5 * 60,
        'send_saved_search_alerts': 5 * 60,
        'generate_blog': 5 * 60,
        'index_jobs': 5 * 60,
    }
    DEFAULT_TIMEOUT = 10 * 60

    def _run(self, label, command_name, *args):
        # Isolate each step: a crash OR a hang (via SIGALRM) is caught here so
        # the remaining steps still run.
        self.stdout.write(label)
        timeout = self.TIMEOUTS.get(command_name, self.DEFAULT_TIMEOUT)

        def _on_alarm(signum, frame):
            raise StepTimeout(f"'{command_name}' exceeded {timeout}s")

        old_handler = signal.signal(signal.SIGALRM, _on_alarm)
        signal.alarm(timeout)
        try:
            call_command(command_name, *args)
        except StepTimeout as e:
            self.stdout.write(self.style.ERROR(f"⏱️ TIMEOUT: {e} — skipping to next step."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Step '{command_name}' failed: {e}"))
        finally:
            signal.alarm(0)  # cancel the alarm
            signal.signal(signal.SIGALRM, old_handler)

    def handle(self, *args, **options):
        self.stdout.write("🚀 STARTING DAILY AUTOPILOT SEQUENCE...")

        # 1. CLEANUP (Clear the deck)
        self._run("\n[1/5] 🧹 Checking for Dead Links & Expired Roles...", 'check_dead_links')
        self._run("      ⏳ Expiring featured/pinned...", 'expire_featured')
        self._run("      🗑️ Cleaning stale jobs...", 'clean_stale_jobs')

        # 2. INGESTION (Get new jobs)
        self._run("\n[2/6] 🏹 Hunting via API (Deep Search)...", 'fetch_jobs')

        # 3. POLISH (Images)
        self._run("\n[3/6] 🎨 Backfilling Logos...", 'update_logos')

        # 4. ALERTS (Email subscribers today's new roles — skips if none)
        self._run("\n[4/6] 📧 Sending Daily Digest to Subscribers...", 'send_daily_digest')
        self._run("      🎯 Sending targeted saved-search alerts...", 'send_saved_search_alerts')

        # 5. CONTENT ENGINE (Automated Blog)
        self._run("\n[5/6] ✍️ Running AI Blog Engine...", 'generate_blog')

        # 6. INDEXING (Ping Google)
        self._run("\n[6/6] 📡 Pinging Google Indexing API...", 'index_jobs')

        self.stdout.write(self.style.SUCCESS("\n✨ AUTOPILOT COMPLETE. System is fresh."))
