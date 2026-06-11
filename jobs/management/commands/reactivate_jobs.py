from django.core.management.base import BaseCommand
from jobs.models import Job

class Command(BaseCommand):
    help = 'Recovery: Re-activates approved jobs that were wrongly hidden by the old dead-link bug.'

    def handle(self, *args, **options):
        # Jobs auto-rejected by the old buggy dead-link checker (check_dead_links
        # tagged its rejections with a "Auto-Removed:" reason). Their links were
        # never actually dead, so restore them to approved/live.
        hidden = Job.objects.filter(screening_status='rejected', screening_reason__startswith='Auto-Removed:')
        count = hidden.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("✅ Nothing to recover. No jobs auto-removed by the dead-link checker were found."))
            return

        hidden.update(screening_status='approved', is_active=True)
        self.stdout.write(self.style.SUCCESS(f"♻️ Recovered {count} jobs. They are now live on the site again."))
