from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.utils.text import slugify
from jobs.models import Category, Tool

class Command(BaseCommand):
    help = 'Repairs the database: Ensures Salesforce/HubSpot exist and clears cache.'

    def handle(self, *args, **options):
        self.stdout.write("🔧 Starting Database Repair...")

        # 1. Clear the cache (Fixes "Stale Data" issues)
        cache.delete('popular_tech_stacks_v2')
        cache.delete('available_countries_v2')
        self.stdout.write("   ✅ Cache Cleared.")

        # 2. Ensure Categories Exist
        cat_automation, _ = Category.objects.get_or_create(
            slug='marketing-automation', 
            defaults={'name': 'Marketing Automation'}
        )
        cat_analytics, _ = Category.objects.get_or_create(
            slug='analytics', 
            defaults={'name': 'Analytics'}
        )

        # 3. FORCE CREATE ESSENTIAL TOOLS (The Fix for your 404)
        # We use update_or_create to fix them even if they exist but are broken.
        
        # Salesforce
        Tool.objects.update_or_create(
            slug='salesforce',
            defaults={
                'name': 'Salesforce',
                'category': cat_automation,
                'logo_url': 'https://www.google.com/s2/favicons?domain=salesforce.com&sz=128'
            }
        )
        self.stdout.write("   ✅ Tool Fixed: Salesforce")

        # HubSpot
        Tool.objects.update_or_create(
            slug='hubspot',
            defaults={
                'name': 'HubSpot',
                'category': cat_automation,
                'logo_url': 'https://www.google.com/s2/favicons?domain=hubspot.com&sz=128'
            }
        )
        self.stdout.write("   ✅ Tool Fixed: HubSpot")

        # Marketo
        Tool.objects.update_or_create(
            slug='marketo',
            defaults={
                'name': 'Marketo',
                'category': cat_automation,
                'logo_url': 'https://www.google.com/s2/favicons?domain=adobe.com&sz=128'
            }
        )
        self.stdout.write("   ✅ Tool Fixed: Marketo")

        self.stdout.write(self.style.SUCCESS('\n✨ SUCCESS: Salesforce link will now work!'))
