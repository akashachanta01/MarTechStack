from django.core.management.base import BaseCommand
from django.core.cache import cache
from jobs.models import Tool, Category

class Command(BaseCommand):
    help = 'Seeds all SEO Pillars across Tiers 1, 2, and 3 based on keyword research.'

    def handle(self, *args, **options):
        self.stdout.write("🏗️ Building SEO Architecture (All Tiers)...")

        # Ensure Categories Exist
        cat_auto, _ = Category.objects.get_or_create(name="Marketing Automation", defaults={'slug': 'marketing-automation'})
        cat_crm, _ = Category.objects.get_or_create(name="CRM & Sales", defaults={'slug': 'crm-sales'})
        cat_data, _ = Category.objects.get_or_create(name="Data & Analytics", defaults={'slug': 'data-analytics'})
        cat_engagement, _ = Category.objects.get_or_create(name="Customer Engagement", defaults={'slug': 'customer-engagement'})

        # Structure: (Name, Slug, Category, Logo, SEO Title, H1 Title, Description)
        pillars = [
            # --- TIER 1 ---
            (
                "Salesforce Administrator", "salesforce-administrator", cat_crm,
                "https://www.google.com/s2/favicons?domain=salesforce.com&sz=128",
                "Salesforce Administrator Jobs (Remote & On-site) - MarTechJobs",
                "Salesforce Administrator Jobs",
                "<p>Search verified <strong>Salesforce Administrator jobs</strong>. We curate the best Salesforce Admin roles, from entry-level to senior positions, ensuring you find the right fit for your technical expertise.</p>"
            ),
            (
                "Salesforce Developer", "salesforce-developer", cat_crm,
                "https://www.google.com/s2/favicons?domain=salesforce.com&sz=128",
                "Salesforce Developer Jobs (Remote & Contract) - MarTechJobs",
                "Salesforce Developer Jobs",
                "<p>Find top-tier <strong>Salesforce Developer jobs</strong>. We track roles requiring expertise in Apex, Visualforce, Lightning Web Components (LWC), and complex integrations.</p>"
            ),
            (
                "MarTech Companies", "companies", cat_auto,
                "https://www.google.com/s2/favicons?domain=martechjobs.io&sz=128",
                "Top MarTech Companies Hiring Now - MarTech SaaS Careers",
                "MarTech Companies to Work For",
                "<p>Explore the best <strong>MarTech companies</strong> and SaaS leaders. Browse our directory of top marketing technology organizations currently hiring for operations and engineering talent.</p>"
            ),
            # --- TIER 2 & ORIGINAL PILLARS ---
            (
                "HubSpot", "hubspot", cat_crm,
                "https://www.google.com/s2/favicons?domain=hubspot.com&sz=128",
                "HubSpot Jobs & Careers (Remote & Contract) - MarTechJobs",
                "HubSpot Jobs & Developer Roles",
                "<p>Searching for <strong>HubSpot jobs</strong>? We curate the best opportunities for HubSpot Administrators, Developers, and RevOps specialists.</p>"
            ),
            (
                "Braze", "braze", cat_engagement,
                "https://www.google.com/s2/favicons?domain=braze.com&sz=128",
                "Braze Jobs & Email Marketing Careers - MarTechJobs",
                "Braze Jobs",
                "<p>Looking for <strong>Braze jobs</strong>? We connect Braze-certified professionals with high-growth brands seeking email specialists and technologists.</p>"
            ),
            (
                "Adobe Experience Platform", "aep", cat_data,
                "https://www.google.com/s2/favicons?domain=adobe.com&sz=128",
                "Adobe Experience Platform Jobs (AEP) - Architects & Engineers",
                "Adobe Experience Platform (AEP) Jobs",
                "<p>Browse high-paying <strong>Adobe Experience Platform jobs</strong>. Find technical AEP Architect and Data Engineer roles.</p>"
            ),
            (
                "Klaviyo", "klaviyo", cat_engagement,
                "https://www.google.com/s2/favicons?domain=klaviyo.com&sz=128",
                "Klaviyo Jobs - Email & SMS Marketing Roles",
                "Klaviyo Jobs",
                "<p>The best <strong>Klaviyo jobs</strong> for eCommerce growth marketers and technical specialists.</p>"
            ),
            # --- TIER 3 ---
            (
                "ROAS Calculator", "roas-calculator", cat_data,
                "https://www.google.com/s2/favicons?domain=martechjobs.io&sz=128",
                "ROAS Calculator - Calculate Return on Ad Spend Online",
                "Free ROAS Calculator",
                "<p>Use our free <strong>ROAS calculator</strong> to measure campaign effectiveness and calculate Return on Ad Spend instantly.</p>"
            )
        ]

        for p in pillars:
            name, slug, category, logo, seo_title, h1, desc = p
            Tool.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'category': category,
                    'logo_url': logo,
                    'seo_title': seo_title,
                    'seo_h1': h1,
                    'description': desc
                }
            )
            self.stdout.write(self.style.SUCCESS(f"   ✅ Seeded: {name}"))

        cache.delete('popular_tech_stacks_v2')
        self.stdout.write(self.style.SUCCESS("\n✨ All SEO Pillars Successfully Updated!"))
