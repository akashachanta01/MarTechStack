from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from django.conf import settings

class Command(BaseCommand):
    help = 'Fixes the database domain to match the production URL for SEO Sitemaps.'

    def handle(self, *args, **options):
        # 1. Get the Site ID (defaults to 1)
        site_id = getattr(settings, 'SITE_ID', 1)
        
        # 2. Get the correct domain from your settings
        # Removes https:// and trailing slashes to get just "martechjobs.io"
        raw_domain = settings.DOMAIN_URL
        clean_domain = raw_domain.replace('https://', '').replace('http://', '').strip('/')
        site_name = "MarTechJobs"

        self.stdout.write(f"🔧 Checking Site ID {site_id}...")
        self.stdout.write(f"   Target Domain: {clean_domain}")

        # 3. Update or Create the Site record
        site, created = Site.objects.update_or_create(
            id=site_id,
            defaults={
                'domain': clean_domain,
                'name': site_name
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f"✅ Created new Site record: {site.domain}"))
        else:
            self.stdout.write(self.style.SUCCESS(f"✅ Updated existing Site record to: {site.domain}"))
            
        self.stdout.write(self.style.WARNING("NOTE: If you see 'no such table: django_site' error, run migrations first."))
