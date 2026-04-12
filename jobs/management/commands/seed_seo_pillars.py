from django.core.management.base import BaseCommand
from django.core.cache import cache
from jobs.models import Tool, Category

class Command(BaseCommand):
    help = 'Seeds massive matrix of SEO Pillars while preserving existing rich keywords.'

    def handle(self, *args, **options):
        self.stdout.write("🏗️ Building Programmatic SEO Architecture...")

        # 1. Establish Categories
        cat_auto, _ = Category.objects.get_or_create(name="Marketing Automation", defaults={'slug': 'marketing-automation'})
        cat_crm, _ = Category.objects.get_or_create(name="CRM & Sales", defaults={'slug': 'crm-sales'})
        cat_data, _ = Category.objects.get_or_create(name="Data & Analytics", defaults={'slug': 'data-analytics'})
        cat_engage, _ = Category.objects.get_or_create(name="Customer Engagement", defaults={'slug': 'customer-engagement'})
        cat_cms, _ = Category.objects.get_or_create(name="CMS & Web", defaults={'slug': 'cms-web'})
        cat_abm, _ = Category.objects.get_or_create(name="ABM & Intent", defaults={'slug': 'abm'})

        count = 0

        # --- 2. THE 50+ TOOL MATRIX (Programmatic Foundation) ---
        tools_matrix = [
            ("Salesforce", "salesforce", cat_crm, "salesforce.com"),
            ("Snowflake", "snowflake", cat_data, "snowflake.com"),
            ("Iterable", "iterable", cat_engage, "iterable.com"),
            ("Customer.io", "customer-io", cat_engage, "customer.io"),
            ("ActiveCampaign", "activecampaign", cat_auto, "activecampaign.com"),
            ("Mailchimp", "mailchimp", cat_engage, "mailchimp.com"),
            ("Eloqua", "eloqua", cat_auto, "oracle.com"),
            ("Segment", "segment", cat_data, "segment.com"),
            ("Tealium", "tealium", cat_data, "tealium.com"),
            ("mParticle", "mparticle", cat_data, "mparticle.com"),
            ("ActionIQ", "actioniq", cat_data, "actioniq.com"),
            ("Hightouch", "hightouch", cat_data, "hightouch.com"),
            ("Fivetran", "fivetran", cat_data, "fivetran.com"),
            ("dbt", "dbt", cat_data, "getdbt.com"),
            ("Google Analytics", "ga4", cat_data, "analytics.google.com"),
            ("Google Tag Manager", "gtm", cat_data, "tagmanager.google.com"),
            ("Tableau", "tableau", cat_data, "tableau.com"),
            ("Looker", "looker", cat_data, "looker.com"),
            ("PowerBI", "powerbi", cat_data, "powerbi.microsoft.com"),
            ("Mixpanel", "mixpanel", cat_data, "mixpanel.com"),
            ("Amplitude", "amplitude", cat_data, "amplitude.com"),
            ("6sense", "6sense", cat_abm, "6sense.com"),
            ("Demandbase", "demandbase", cat_abm, "demandbase.com"),
            ("ZoomInfo", "zoominfo", cat_crm, "zoominfo.com"),
            ("Clearbit", "clearbit", cat_data, "clearbit.com"),
            ("Apollo", "apollo", cat_crm, "apollo.io"),
            ("Outreach", "outreach", cat_crm, "outreach.io"),
            ("Salesloft", "salesloft", cat_crm, "salesloft.com"),
            ("LeanData", "leandata", cat_crm, "leandata.com"),
            ("Chili Piper", "chili-piper", cat_crm, "chilipiper.com"),
            ("Drift", "drift", cat_engage, "drift.com"),
            ("Intercom", "intercom", cat_engage, "intercom.com"),
            ("Optimizely", "optimizely", cat_cms, "optimizely.com"),
            ("VWO", "vwo", cat_cms, "vwo.com"),
            ("WordPress", "wordpress", cat_cms, "wordpress.org"),
            ("Contentful", "contentful", cat_cms, "contentful.com"),
            ("Webflow", "webflow", cat_cms, "webflow.com"),
            ("Zapier", "zapier", cat_auto, "zapier.com"),
            ("Make", "make", cat_auto, "make.com"),
            ("Tray.io", "tray", cat_auto, "tray.io"),
            ("Sprout Social", "sprout-social", cat_engage, "sproutsocial.com"),
            ("Hootsuite", "hootsuite", cat_engage, "hootsuite.com"),
            ("Sprinklr", "sprinklr", cat_engage, "sprinklr.com"),
            ("Airtable", "airtable", cat_data, "airtable.com")
        ]

        for name, slug, category, domain in tools_matrix:
            Tool.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'category': category,
                    'logo_url': f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
                    'seo_title': f"{name} Jobs & Careers (Remote & On-site) - MarTechJobs",
                    'seo_h1': f"Top {name} Jobs",
                    'description': f"<p>Search active <strong>{name} jobs</strong> and careers. We curate the best marketing operations, analytics, and engineering roles requiring expertise in {name}. Browse remote and on-site opportunities below.</p>"
                }
            )
            count += 1

        # --- 3. EXISTING RICH PILLARS (Preserved & Overriding Generic Ones) ---
        rich_pillars = [
            ("Salesforce Administrator", "salesforce-administrator", cat_crm, "salesforce.com", "Salesforce Administrator Jobs (Remote & On-site) - MarTechJobs", "Salesforce Administrator Jobs", "<p>Search verified <strong>Salesforce Administrator jobs</strong>. We curate the best Salesforce Admin roles, from entry-level to senior positions, ensuring you find the right fit for your technical expertise.</p>"),
            ("Salesforce Developer", "salesforce-developer", cat_crm, "salesforce.com", "Salesforce Developer Jobs (Remote & Contract) - MarTechJobs", "Salesforce Developer Jobs", "<p>Find top-tier <strong>Salesforce Developer jobs</strong>. We track roles requiring expertise in Apex, Visualforce, Lightning Web Components (LWC), and complex integrations.</p>"),
            ("MarTech Companies", "companies", cat_auto, "martechjobs.io", "Top MarTech Companies Hiring Now - MarTech SaaS Careers", "MarTech Companies to Work For", "<p>Explore the best <strong>MarTech companies</strong> and SaaS leaders. Browse our directory of top marketing technology organizations currently hiring for operations and engineering talent.</p>"),
            ("HubSpot", "hubspot", cat_crm, "hubspot.com", "HubSpot Jobs & Careers (Remote & Contract) - MarTechJobs", "HubSpot Jobs & Developer Roles", "<p>Searching for <strong>HubSpot jobs</strong>? We curate the best opportunities for HubSpot Administrators, Developers, and RevOps specialists.</p>"),
            ("Salesforce Marketing Cloud", "salesforce-marketing-cloud", cat_auto, "salesforce.com", "Salesforce Marketing Cloud Jobs (SFMC) - Consultants & Architects", "Salesforce Marketing Cloud Jobs", "<p>Find high-paying <strong>Salesforce Marketing Cloud jobs</strong>. Whether you are a <strong>Certified Email Specialist</strong>, a Technical Architect, or an SFMC Consultant, we track the top open roles at enterprise companies and agencies.</p>"),
            ("Marketo", "marketo", cat_auto, "adobe.com", "Marketo Jobs & MCE Career Opportunities", "Marketo Jobs", "<p>Browse the latest <strong>Marketo jobs</strong> for Marketing Automation Managers and MCE certified experts. From campaign execution to full instance architecture, find your next role in the Adobe ecosystem here.</p>"),
            ("Braze", "braze", cat_engage, "braze.com", "Braze Jobs & Email Marketing Careers - MarTechJobs", "Braze Jobs", "<p>Looking for <strong>Braze jobs</strong>? We connect Braze-certified professionals with high-growth brands seeking email specialists and technologists.</p>"),
            ("Adobe Experience Platform", "aep", cat_data, "adobe.com", "Adobe Experience Platform Jobs (AEP) - Architects & Engineers", "Adobe Experience Platform (AEP) Jobs", "<p>Browse high-paying <strong>Adobe Experience Platform jobs</strong>. Find technical AEP Architect and Data Engineer roles within the Adobe Experience Cloud ecosystem.</p>"),
            ("Adobe Experience Manager", "adobe-experience-manager", cat_data, "adobe.com", "Adobe Experience Manager (AEM) Jobs", "AEM Jobs", "<p>Find technical <strong>Adobe Experience Manager (AEM)</strong> roles. From AEM Developers to Content Authors and Architects, browse the best opportunities in the Adobe Experience Cloud.</p>"),
            ("Pardot", "pardot", cat_auto, "salesforce.com", "Pardot Admin Jobs (Account Engagement)", "Pardot Jobs", "<p>Specialized <strong>Pardot Admin</strong> roles (now Marketing Cloud Account Engagement). Connect with B2B companies looking for experts in lead scoring, grading, and engagement studio.</p>"),
            ("Klaviyo", "klaviyo", cat_engage, "klaviyo.com", "Klaviyo Jobs - Email & SMS Marketing Roles", "Klaviyo Jobs", "<p>The best <strong>Klaviyo jobs</strong> for eCommerce growth marketers and technical specialists.</p>"),
            ("ROAS Calculator", "roas-calculator", cat_data, "martechjobs.io", "ROAS Calculator - Calculate Return on Ad Spend Online", "Free ROAS Calculator", "<p>Use our free <strong>ROAS calculator</strong> to measure campaign effectiveness and calculate Return on Ad Spend instantly.</p>")
        ]

        for name, slug, category, domain, seo_title, h1, desc in rich_pillars:
            Tool.objects.update_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'category': category,
                    'logo_url': f"https://www.google.com/s2/favicons?domain={domain}&sz=128",
                    'seo_title': seo_title,
                    'seo_h1': h1,
                    'description': desc
                }
            )
            count += 1

        cache.clear()
        self.stdout.write(self.style.SUCCESS(f"\n✨ Successfully seeded {count} tools and preserved all important rich SEO pillars!"))
