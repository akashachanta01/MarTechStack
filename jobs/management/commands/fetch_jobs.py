from django.core.management.base import BaseCommand
import requests
import time
from datetime import datetime, timedelta
from django.utils import timezone
import dateutil.parser  # Required for parsing diverse date formats
from jobs.models import Job, Tool
from jobs.screener import MarTechScreener

class Command(BaseCommand):
    help = 'Direct-to-Source Job Fetcher (Greenhouse + Lever) with Date Filter'

    def handle(self, *args, **options):
        self.stdout.write("🚀 Starting Job Sync (Last 28 Days Only)...")
        
        self.screener = MarTechScreener()
        self.total_scanned = 0
        self.total_added = 0
        
        # Calculate the cutoff date (28 days ago)
        self.cutoff_date = timezone.now() - timedelta(days=28)
        self.stdout.write(f"📅 Skipping jobs posted before: {self.cutoff_date.date()}")

        self.tool_cache = {t.name.lower(): t for t in Tool.objects.all()}
        self.stdout.write(f"ℹ️  Loaded {len(self.tool_cache)} tools from database.")

        # --- TARGET COMPANIES ---
        greenhouse_targets = [
            'segment', 'twilio', 'braze', 'mparticle', 'tealium', 
            'amplitude', 'mixpanel', 'hubspot', 'klaviyo', 'activecampaign',
            'hashicorp', 'airtable', 'figma', 'notion', 'stripe', 'plaid', 
            'gusto', 'zapier', 'webflow', 'dbt', 'fivetran', 'snowflake',
            'databricks', 'confluent', 'redis', 'mongodb', 'gitlab'
        ]

        lever_targets = [
            'atlassian', 'netflix', 'lyft', 'twitch', 'shopify', 
            'palantir', 'box', 'eventbrite', 'udemy', 'coursera',
            'affirm', 'benchling', 'instacart', 'kp', 'scale'
        ]

        # 1. Run Greenhouse
        for company in greenhouse_targets:
            self.fetch_greenhouse(company)
            time.sleep(0.5) 

        # 2. Run Lever
        for company in lever_targets:
            self.fetch_lever(company)
            time.sleep(0.5)

        self.stdout.write(self.style.SUCCESS(f"\n✨ Sync Complete!"))
        self.stdout.write(f"   - Scanned: {self.total_scanned} jobs")
        self.stdout.write(f"   - Saved:   {self.total_added} fresh MarTech matches")

    # ---------------------------------------------------------
    # WORKER: Greenhouse
    # ---------------------------------------------------------
    def fetch_greenhouse(self, board_token):
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200: return

            jobs = response.json().get('jobs', [])
            self.stdout.write(f"   🔎 [Greenhouse] {board_token}: Checking {len(jobs)} roles...")

            for item in jobs:
                self.total_scanned += 1
                
                # DATE CHECK
                if not self.is_fresh(item.get('updated_at')):
                    continue

                title = item.get('title')
                location_obj = item.get('location', {})
                location = location_obj.get('name') if location_obj else "Remote"
                description = item.get('content', '')
                apply_url = item.get('absolute_url')

                self.process_job(title, board_token.capitalize(), location, description, apply_url, "Greenhouse")

        except Exception as e:
            self.stdout.write(f"   ❌ Error fetching {board_token}: {e}")

    # ---------------------------------------------------------
    # WORKER: Lever
    # ---------------------------------------------------------
    def fetch_lever(self, board_token):
        url = f"https://api.lever.co/v0/postings/{board_token}?mode=json"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200: return

            jobs = response.json()
            self.stdout.write(f"   🔎 [Lever] {board_token}: Checking {len(jobs)} roles...")

            for item in jobs:
                self.total_scanned += 1
                
                # DATE CHECK (Lever uses 'createdAt')
                # Leverage normally returns a timestamp in milliseconds
                created_at = item.get('createdAt')
                if created_at:
                    # Convert ms timestamp to datetime
                    job_date = datetime.fromtimestamp(created_at / 1000.0, tz=timezone.utc)
                    if job_date < self.cutoff_date:
                        continue
                
                title = item.get('text')
                location = item.get('categories', {}).get('location', 'Remote')
                description = item.get('description', '')
                apply_url = item.get('hostedUrl')

                self.process_job(title, board_token.capitalize(), location, description, apply_url, "Lever")

        except Exception as e:
            self.stdout.write(f"   ❌ Error fetching {board_token}: {e}")

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------
    def is_fresh(self, date_str):
        """Returns True if the job is newer than the cutoff date"""
        if not date_str: return True # If no date, assume fresh to be safe
        try:
            job_date = dateutil.parser.parse(date_str)
            if job_date.tzinfo is None:
                job_date = timezone.make_aware(job_date)
            return job_date >= self.cutoff_date
        except:
            return True # Fallback if parse fails

    def process_job(self, title, company, location, description, apply_url, source):
        if Job.objects.filter(apply_url=apply_url).exists():
            return

        analysis = self.screener.screen_job(title, description)
        
        if not analysis['is_match']:
            return

        job = Job.objects.create(
            title=title,
            company=company,
            location=location,
            description=description,
            apply_url=apply_url,
            tags=f"{source}, {analysis['role_type']}",
            is_active=True
        )

        linked_count = 0
        for tool_name in analysis['stack']:
            db_tool = self.tool_cache.get(tool_name.lower())
            if db_tool:
                job.tools.add(db_tool)
                linked_count += 1
        
        self.total_added += 1
        self.stdout.write(f"      ✅ MATCH: {title} ({linked_count} tools)")
