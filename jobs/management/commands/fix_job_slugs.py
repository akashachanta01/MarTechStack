from django.core.management.base import BaseCommand
from jobs.models import Job

class Command(BaseCommand):
    help = 'Backfills missing slugs for existing jobs to fix broken links.'

    def handle(self, *args, **options):
        self.stdout.write("🔧 Checking for jobs with missing slugs...")

        # Find jobs where slug is null or empty
        jobs = Job.objects.filter(slug__isnull=True) | Job.objects.filter(slug='')
        count = jobs.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("✅ All jobs already have slugs. No action needed."))
            return

        self.stdout.write(f"⚠️ Found {count} jobs with missing slugs. Fixing now...")

        fixed_count = 0
        for job in jobs:
            try:
                # Calling save() triggers the logic in models.py to generate the slug
                job.save()
                fixed_count += 1
                if fixed_count % 10 == 0:
                    self.stdout.write(f"   Processed {fixed_count}...")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ❌ Error fixing Job {job.id}: {e}"))

        self.stdout.write(self.style.SUCCESS(f"✨ Success! Fixed {fixed_count} jobs. Links should work now."))
