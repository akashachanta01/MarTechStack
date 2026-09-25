"""Daily data-quality pass over jobs already in the database (site audit batch 2).

- readable company names, requisition codes out of titles, tidy locations
  (the same rules Job.save() applies to new jobs)
- salary from the posting's own text when the ATS gave none
- one live copy per company + title + location (newest wins)

Safe to re-run; `--dry-run` reports without writing.
"""
from collections import defaultdict

from django.core.management.base import BaseCommand

from jobs.ingest_quality import clean_title, display_company, extract_salary, tidy_location
from jobs.models import Job, normalize_location


class Command(BaseCommand):
    help = "Clean company names, titles, locations, salaries; remove live duplicates."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        live = Job.objects.filter(is_active=True, screening_status="approved")
        counts = defaultdict(int)

        for job in live.only("id", "title", "company", "location", "salary_range", "description", "country"):
            changes = {}
            title, company = clean_title(job.title), display_company(job.company)
            if title != job.title:
                changes["title"] = title
            if company != job.company:
                changes["company"] = company
            if job.location:
                loc = normalize_location(tidy_location(job.location))
                if loc != job.location:
                    changes["location"] = loc
            from jobs.geo import country_code
            code = country_code(job.location or "")
            if code and code != job.country:
                changes["country"] = code
            if not job.salary_range:
                pay = extract_salary(job.description)
                if pay:
                    changes["salary_range"] = pay
            for field in changes:
                counts[field] += 1
            if changes and not dry:
                # .update(): no re-sanitising of descriptions or slug changes.
                Job.objects.filter(pk=job.pk).update(**changes)

        # Tag every live job with the platforms its description asks for (same
        # engine as the Resume Scanner). The AI screener only tagged ~40% of
        # jobs, so tool pages (e.g. "SFMC jobs") showed a fraction of the roles.
        counts["tools_added"] = self._tag_tools(live, dry)
        counts["locations_resolved"] = self._resolve_workday_multi(live, dry)

        # Clearly non-MarTech roles the AI screener let through (e.g. factory
        # welders, German medical-device "AEMP" jobs matched as AEM).
        import re as _re
        offtopic_rx = _re.compile(r"\b(welder|brazer|brazing|forklift|warehouse associate|truck driver|"
                                  r"registered nurse|medizinprodukt\w*|aufbereitung\w*)\b", _re.I)
        offtopic = [pk for pk, t in live.values_list("id", "title") if offtopic_rx.search(t or "")]
        counts["offtopic_removed"] = len(offtopic)
        if offtopic and not dry:
            Job.objects.filter(id__in=offtopic).update(
                is_active=False, screening_reason="Off-topic role (not MarTech)")

        groups = defaultdict(list)
        for pk, t, c, l, created in live.values_list("id", "title", "company", "location", "created_at"):
            groups[((c or "").lower(), (t or "").lower(), (l or "").lower())].append((created, pk))
        dupes = [pk for rows in groups.values() if len(rows) > 1 for _, pk in sorted(rows)[:-1]]
        counts["duplicates"] = len(dupes)
        if dupes and not dry:
            Job.objects.filter(id__in=dupes).update(
                is_active=False, screening_reason="Duplicate of a newer live listing")

        if not dry:
            # Role pages are built from titles + tool tags: rebuild them now.
            from django.core.cache import cache
            cache.delete_many(["auto_roles:v1", "tool_roles:v2", "available_countries_v4"])
        verb = "Would change" if dry else "Changed"
        self.stdout.write(self.style.SUCCESS(
            f"🧽 {verb}: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())) if counts else "🧽 Nothing to clean."))

    def _tag_tools(self, live, dry):
        from django.utils.text import slugify
        from jobs.models import Category, Tool
        from jobs.resume_match import _job_entry
        from jobs.tool_catalog import resolve_tool_name
        tools = {t.name.lower(): t for t in Tool.objects.all()}
        category = None
        added = 0
        for job in live.prefetch_related("tools"):
            try:
                terms = _job_entry(job)[0]["terms"]
            except Exception:
                continue
            have = {t.id for t in job.tools.all()}
            for term, kind in terms.items():
                if kind != "platform":
                    continue
                canon = resolve_tool_name(term)
                if not canon:
                    continue
                tool = tools.get(canon.lower())
                if tool is None:
                    if dry:
                        added += 1
                        continue
                    if category is None:
                        category, _ = Category.objects.get_or_create(name="MarTech", defaults={"slug": "martech"})
                    tool, _ = Tool.objects.get_or_create(name=canon, defaults={"slug": slugify(canon), "category": category})
                    tools[canon.lower()] = tool
                if tool.id not in have:
                    added += 1
                    have.add(tool.id)
                    if not dry:
                        job.tools.add(tool)
        return added

    def _resolve_workday_multi(self, live, dry, limit=150):
        """Workday lists multi-site roles as "N Locations", stored as "Multiple
        locations" (no country). Ask Workday for the primary location once."""
        import re
        import requests
        from jobs.geo import country_code
        rx = re.compile(r"https://([^./]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([^/?#]+)/(job/[^?#]+)")
        fixed = 0
        for job in live.filter(location__iexact="Multiple locations", apply_url__contains="myworkdayjobs.com")[:limit]:
            m = rx.match(job.apply_url or "")
            if not m:
                continue
            tenant, wd, site, path = m.groups()
            try:
                r = requests.get(f"https://{tenant}.{wd}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/{path}",
                                 headers={"Accept": "application/json"}, timeout=10)
                info = (r.json().get("jobPostingInfo") or {}) if r.status_code == 200 else {}
            except (requests.RequestException, ValueError):
                continue
            primary = str(info.get("location") or "").strip()
            if not primary or re.match(r"^\s*\d+\s+locations?\s*$", primary, re.I):
                continue
            loc = normalize_location(tidy_location(primary))
            code = country_code(loc)
            if not dry:
                Job.objects.filter(pk=job.pk).update(location=loc, country=code or job.country)
            fixed += 1
        return fixed
