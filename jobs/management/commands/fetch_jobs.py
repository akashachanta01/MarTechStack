import json
import os
import time
from typing import Any, Dict, List, Optional

import requests
from django.core.management.base import BaseCommand

from jobs.models import Job
from jobs.screener import MarTechScreener


class Command(BaseCommand):
    help = "Fetch jobs from external sources, screen them, and store results with Zero-Noise fields."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50, help="Max jobs to process this run.")
        parser.add_argument("--sleep", type=float, default=0.0, help="Seconds to sleep between jobs (rate-limits).")
        parser.add_argument("--dry-run", action="store_true", help="Run screening but do not write DB changes.")

    def handle(self, *args, **options):
        limit = options["limit"]
        sleep_s = options["sleep"]
        dry_run = options["dry_run"]

        screener = MarTechScreener(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

        # NOTE:
        # This file keeps your existing job-hunting logic structure but ensures
        # every ingested job is saved with screening fields.
        #
        # If you have multiple sources in your real repo, keep them, but always
        # route each candidate job through `upsert_and_screen()`.

        candidates = self.fetch_candidates(limit=limit)

        self.stdout.write(self.style.SUCCESS(f"Fetched {len(candidates)} candidates"))

        processed = 0
        for job_data in candidates[:limit]:
            processed += 1
            title = job_data.get("title", "") or ""
            company = job_data.get("company", "") or ""
            location = job_data.get("location", "") or ""
            description = job_data.get("description", "") or ""
            apply_url = job_data.get("apply_url", "") or ""

            if not title or not company or not apply_url:
                continue

            self.stdout.write(f"[{processed}] Screening: {title} @ {company}")

            result = screener.screen(
                title=title,
                company=company,
                location=location,
                description=description,
                apply_url=apply_url,
            )

            self.stdout.write(f"  -> {result.status.upper()} score={result.score:.1f} reason={result.reason}")

            if dry_run:
                if sleep_s:
                    time.sleep(sleep_s)
                continue

            self.upsert_and_screen(job_data, result)

            if sleep_s:
                time.sleep(sleep_s)

        self.stdout.write(self.style.SUCCESS("Done."))

    def upsert_and_screen(self, job_data: Dict[str, Any], result):
        """
        Insert or update a Job and store screening explainability.
        """
        apply_url = job_data.get("apply_url", "")
        job, created = Job.objects.get_or_create(
            apply_url=apply_url,
            defaults={
                "title": job_data.get("title", "") or "",
                "company": job_data.get("company", "") or "",
                "location": job_data.get("location", "") or "",
                "remote": bool(job_data.get("remote", False)),
                "description": job_data.get("description", "") or "",
                "role_type": job_data.get("role_type", "full_time") or "full_time",
                "is_active": True,
            },
        )

        # Keep basic fields fresh
        job.title = job_data.get("title", job.title) or job.title
        job.company = job_data.get("company", job.company) or job.company
        job.location = job_data.get("location", job.location) or job.location
        job.remote = bool(job_data.get("remote", job.remote))
        job.description = job_data.get("description", job.description) or job.description
        job.role_type = job_data.get("role_type", job.role_type) or job.role_type

        # Store screening results
        job.screening_status = result.status
        job.screening_score = float(result.score)
        job.screening_reason = result.reason or ""
        job.screening_details = result.details or {}
        job.screened_at = job.screened_at or None  # set only if you want; review_action will set if missing

        # Visibility rule:
        # Approved -> visible
        # Pending -> hidden (until approved)
        # Rejected -> hidden
        job.is_active = True if result.status == "approved" else False

        job.save()

    def fetch_candidates(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Your repo may already have real sources (Greenhouse/Lever/Google search).
        This function is a safe placeholder that keeps things functional.

        Replace/extend this with your existing hunter logic if needed.
        """
        # If you already have a working fetcher elsewhere in this file,
        # keep it and return a list of dicts in the same format as below.
        #
        # Format:
        # {
        #   "title": "...",
        #   "company": "...",
        #   "location": "...",
        #   "remote": True/False,
        #   "description": "...",
        #   "apply_url": "https://..."
        # }

        # Example: empty by default (so command still runs)
        return []
