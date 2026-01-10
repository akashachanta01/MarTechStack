from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.core.cache import cache
from jobs.models import Tool, Category

class Command(BaseCommand):
    help = 'Seeds the 7 Core SEO Pillars with high-intent keywords from Ahrefs research.'

    def handle(self, *args, **options):
        self.stdout.write("🏗️  Building SEO Architecture (The 7 Pillars)...")

        # 1. Ensure Categories Exist
        cat_auto, _ = Category.objects.get_or_create(name="Marketing Automation", defaults={'slug': 'marketing-automation'})
        cat_crm, _ = Category.objects.get_or_create(name="CRM & Sales", defaults={'slug': 'crm-sales'})
        cat_data, _ = Category.objects.get_or_create(name="Data & Analytics", defaults={'slug': 'data-analytics'})
        cat_engagement, _ = Category.objects.get_or_create(name="Customer Engagement", defaults={'slug': 'customer-engagement'})

        # 2. Define the SEO Pillars (Based on your Screenshots)
        # Structure: (Name, Slug, Category, Logo, SEO Title, H1 Title, Description)
        pillars = [
            (
                "HubSpot", "hubspot", cat_crm,
                "https://www.google.com/s2/favicons?domain=hubspot.com&sz=128",
                "HubSpot Jobs & Careers (Remote & Contract) - MarTechJobs",
                "HubSpot Jobs & Developer Roles",
                """<p>Searching for <strong>HubSpot jobs</strong>? We curate the best opportunities for HubSpot Administrators, Developers, and RevOps specialists. Whether you are looking for a remote HubSpot Consultant role or an in-house Manager position, browse our verified listings below.</p>"""
            ),
            (
                "Salesforce Marketing Cloud", "salesforce-marketing-cloud", cat_auto,
                "https://www.google.com/s2/favicons?domain=salesforce.com&sz=128",
                "Salesforce Marketing Cloud Jobs (SFMC) - Consultants & Architects",
                "Salesforce Marketing Cloud Jobs",
                """<p>Find high-paying <strong>Salesforce Marketing Cloud jobs</strong>. Whether you are a <strong>Certified Email Specialist</strong>, a Technical Architect, or an SFMC Consultant, we track the top open roles at enterprise companies and agencies.</p>"""
            ),
            (
                "Marketo", "marketo", cat_auto,
                "https://www.google.com/s2/favicons?domain=adobe.com&sz=128",
                "Marketo Jobs & MCE Career Opportunities",
                "Marketo Jobs",
                """<p>Browse the latest <strong>Marketo jobs</strong> for Marketing Automation Managers and MCE certified experts. From campaign execution to full instance architecture, find your next role in the Adobe ecosystem here.</p>"""
            ),
            (
                "Braze", "braze", cat_engagement,
                "https://www.google.com/s2/favicons?domain=braze.com&sz=128",
                "Braze Jobs & Email Marketing Careers",
                "Braze Jobs",
                """<p>Looking for <strong>Braze careers</strong>? While Braze itself is a great company, thousands of high-growth brands use Braze and need specialized talent. Find <strong>Braze Email Specialist</strong> and Technologist roles below.</p>"""
            ),
            (
                "Klaviyo", "klaviyo", cat_engagement,
                "https://www.google.com/s2/favicons?domain=klaviyo.com&sz=128",
                "Klaviyo Jobs - Email & SMS Marketing Roles",
                "Klaviyo Jobs",
                """<p>The best <strong>Klaviyo jobs</strong> for eCommerce growth marketers and technical specialists. Find remote opportunities working with the leading eComm data platform.</p>"""
            ),
            (
                "Pardot", "pardot", cat_auto,
                "https://www.google.com/s2/favicons?domain=salesforce.com&sz=128",
                "Pardot Admin Jobs (Account Engagement)",
                "Pardot Jobs",
                """<p>Specialized <strong>Pardot Admin</strong> roles (now Marketing Cloud Account Engagement). Connect with B2B companies looking for experts in lead scoring, grading, and engagement studio.</p>"""
            ),
            (
                "Adobe Experience Manager", "adobe-experience-manager", cat_data,
                "https://www.google.com/s2/favicons?domain=adobe.com&sz=128",
                "Adobe Experience Manager (AEM) Jobs",
                "AEM Jobs",
                """<p>Find technical <strong>Adobe Experience Manager (AEM)</strong> roles. From AEM Developers to Content Authors and Architects, browse the best opportunities in the Adobe Experience Cloud.</p>"""
            )
        ]

        for p in pillars:
            name, slug, category, logo, seo_title, h1, desc = p
            
            tool, created = Tool.objects.update_or_create(
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
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"   ✅ {action}: {name}"))

        # Clear cache to ensure menus update
        cache.delete('popular_tech_stacks_v2')
        self.stdout.write(self.style.SUCCESS("\n✨ SEO Pillars Seeded Successfully!"))
