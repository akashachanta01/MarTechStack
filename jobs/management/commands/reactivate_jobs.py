from django.core.management.base import BaseCommand
from jobs.models import Job

class Command(BaseCommand):
    help = 'Recovery: Re-activates approved jobs that were wrongly hidden by the old dead-link bug.'

    def handle(self, *args, **options):
        # Jobs that passed screening (status "approved") but got flipped to
        # is_active=False by the buggy dead-link checker. Their links were never
        # actually dead, so bring them back to the live site.
        hidden = Job.objects.filter(screening_status='approved', is_active=False)
        count = hidden.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("✅ Nothing to recover. No approved-but-hidden jobs found."))
            return

        hidden.update(is_active=True)
        self.stdout.write(self.style.SUCCESS(f"♻️ Recovered {count} jobs. They are now live on the site again."))
