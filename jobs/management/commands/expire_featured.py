from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from jobs.models import Job

class Command(BaseCommand):
    help = 'Downgrades Pinned jobs after 7 days and Featured status after 30 days.'

    def handle(self, *args, **options):
        now = timezone.now()
        
        # --- RULE 1: Un-Pin jobs older than 7 days ---
        # Strategy: They keep "is_featured" (yellow) but lose "is_pinned" (top spot).
        pin_cutoff = now - timedelta(days=7)
        pinned_jobs = Job.objects.filter(is_pinned=True, created_at__lt=pin_cutoff)
        
        pinned_count = pinned_jobs.count()
        if pinned_count > 0:
            pinned_jobs.update(is_pinned=False)
            self.stdout.write(self.style.SUCCESS(f"🔻 Un-pinned {pinned_count} jobs (older than 7 days)."))
        else:
            self.stdout.write("✅ No pinned jobs to expire.")

        # --- RULE 2: Remove "Featured" styling after 30 days ---
        # Strategy: They become standard listings (white background).
        feature_cutoff = now - timedelta(days=30)
        featured_jobs = Job.objects.filter(is_featured=True, created_at__lt=feature_cutoff)
        
        featured_count = featured_jobs.count()
        if featured_count > 0:
            featured_jobs.update(is_featured=False)
            self.stdout.write(self.style.SUCCESS(f"⚪ Removed highlight from {featured_count} jobs (older than 30 days)."))
        else:
            self.stdout.write("✅ No featured jobs to expire.")
