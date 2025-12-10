from django.core.management.base import BaseCommand
from django.utils.text import slugify
from jobs.models import Category, Tool

class Command(BaseCommand):
    help = 'Populates the database with initial MarTech categories and tools'

    def handle(self, *args, **options):
        # Your Taxonomy Data
        taxonomy = {
            "Marketing Automation": [
                "Marketo", "HubSpot", "Salesforce Marketing Cloud", 
                "Braze", "Iterable", "Eloqua", "Klaviyo"
            ],
            "Analytics & Data Platforms": [
                "Adobe Analytics", "Google Analytics (GA4)", "Mixpanel", 
                "Amplitude", "Heap", "Tableau", "Looker"
            ],
            "Customer Data & Personalization": [
                "Segment", "Adobe Experience Platform", "Adobe Target", 
                "Tealium", "mParticle", "Salesforce Data Cloud", "Optimizely"
            ],
            "E-commerce Platforms": [
                "Shopify Plus", "Magento", "BigCommerce", 
                "Salesforce Commerce Cloud", "WooCommerce"
            ],
            "CRM & Sales Enablement": [
                "Salesforce CRM", "HubSpot CRM", "Outreach", 
                "Salesloft", "Gong", "Pipedrive"
            ],
            "Content & SEO Tools": [
                "Contentful", "WordPress", "Semrush", 
                "Ahrefs", "Strapi", "Sanity"
            ],
            "Ad Tech & Media": [
                "Google Ads", "Facebook Ads Manager", "Trade Desk", 
                "LinkedIn Campaign Manager"
            ]
        }

        self.stdout.write("Starting population...")

        for cat_name, tools_list in taxonomy.items():
            # 1. Create or Get the Category
            category, created = Category.objects.get_or_create(
                slug=slugify(cat_name),
                defaults={'name': cat_name}
            )
            
            if created:
                self.stdout.write(f"Created Category: {cat_name}")

            # 2. Create the Tools for this Category
            for tool_name in tools_list:
                tool, t_created = Tool.objects.get_or_create(
                    slug=slugify(tool_name),
                    defaults={
                        'name': tool_name,
                        'category': category
                    }
                )
                if t_created:
                    self.stdout.write(f" - Added Tool: {tool_name}")

        self.stdout.write(self.style.SUCCESS('Successfully populated MarTech taxonomy!'))