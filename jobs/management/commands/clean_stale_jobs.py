import time
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from jobs.models import Job

class Command(BaseCommand):
    help = 'Flags active jobs older than 60 days for re-review (demotes them to pending).'

    def handle(self, *args, **options):
        self.stdout.write("🧹 Starting Stale Job Cleanup...")

        # Define the cutoff date: 60 days ago
        cutoff_date = timezone.now() - timedelta(days=60)

        # Find jobs that are currently active (approved) AND older than the cutoff
        stale_jobs = Job.objects.filter(
            is_active=True,
            screening_status='approved',
            created_at__lt=cutoff_date
        )
        
        count = stale_jobs.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS(f"✅ Found 0 jobs older than 60 days. Database is clean."))
            return

        self.stdout.write(self.style.WARNING(f"⚠️ Found {count} jobs older than 60 days. Demoting to Pending..."))

        # Perform the update
        updated_count = stale_jobs.update(
            screening_status='pending',
            is_active=False
        )

        self.stdout.write(self.style.SUCCESS(f"✨ Successfully demoted {updated_count} jobs. They are now hidden and available for review in the Admin queue."))


### New Workflow: Run the script periodically, then review the pending jobs.
# 1. Run the cleaner:
#    python manage.py clean_stale_jobs
#
# 2. Go to your Admin -> Jobs (or Review Queue)
# 3. Filter by 'Pending Review' and review the old jobs that were just flagged.
