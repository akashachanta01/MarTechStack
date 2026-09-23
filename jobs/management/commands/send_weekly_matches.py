"""
Weekly personal "new jobs you match" email for members with a saved resume.

Runs Mondays from run_daily_tasks, BEFORE the generic weekly digest; anyone
emailed here is skipped by the digest that week. Never sends an empty email:
members with no strong new match that week just get the generic digest.

  python manage.py send_weekly_matches --dry-run
"""
import time
from datetime import timedelta

from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.utils import timezone

STRONG_RATIO = 0.8
MAX_JOBS = 6


def _week_key():
    y, w, _ = timezone.now().isocalendar()
    return f"weekly_matches_sent:{y}-{w}"


def already_sent_this_week():
    return set(cache.get(_week_key()) or [])


class Command(BaseCommand):
    help = "Email members the new jobs from the last 7 days that match their saved resume 80%+"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        from accounts.models import UserResume
        from jobs.ats_match import extract_terms
        from jobs.emails import get_digest_recipients, send_html_email
        from jobs.models import Job
        from jobs.resume_match import job_requirements

        since = timezone.now() - timedelta(days=options["days"])
        new_ids = set(Job.objects.filter(is_active=True, screening_status="approved",
                                         went_live_at__gte=since).values_list("id", flat=True))
        if not new_ids:
            self.stdout.write("No new jobs this week — nothing to send.")
            return
        reqs, _ = job_requirements(budget_s=None)          # cron: compute everything
        new_reqs = {j: r for j, r in reqs.items() if j in new_ids and r["terms"]}
        allowed = {e.lower() for e in get_digest_recipients()}   # honours unsubscribes/suppression

        sent_to = already_sent_this_week()
        sent = 0
        for res in UserResume.objects.select_related("user").iterator():
            email = (res.user.email or "").lower()
            if not email or email not in allowed or email in sent_to:
                continue
            have = set(extract_terms(res.text).keys())
            picks, gap_count = [], {}
            for j, r in new_reqs.items():
                need = set(r["terms"])
                hit = len(need & have)
                ratio = hit / len(need)
                if ratio >= 0.5:
                    for t in need - have:
                        gap_count[t] = gap_count.get(t, 0) + 1
                if ratio >= STRONG_RATIO:
                    picks.append({"id": j, "title": r["title"], "company": r["company"], "slug": r["slug"],
                                  "where": r["where"], "matched": hit, "required": len(need),
                                  "missing": sorted(need - have)[:2]})
            if not picks:
                continue
            picks.sort(key=lambda p: (-(p["matched"] / p["required"]), -p["required"]))
            picks = picks[:MAX_JOBS]
            top_gap = max(gap_count.items(), key=lambda kv: kv[1]) if gap_count else None
            n = len(picks)
            subject = (f"{n} new MarTech jobs you match 80%+" if n > 1 else "A new MarTech job you match 80%+")
            first = (res.user.first_name or "").strip()
            if first:
                subject += f", {first}"
            if options["dry_run"]:
                self.stdout.write(f"  would email {email}: {n} match(es); top gap: {top_gap}")
                continue
            ok = send_html_email(
                subject=subject, template_name="emails/weekly_matches.html",
                context={"jobs": picks, "count": n, "first_name": first,
                         "top_gap": top_gap[0] if top_gap else "", "top_gap_n": top_gap[1] if top_gap else 0},
                to_email=[email], unsubscribe_email=email,
            )
            if ok:
                sent += 1
                sent_to.add(email)
                cache.set(_week_key(), list(sent_to), 9 * 86400)
            time.sleep(0.3)
        self.stdout.write(self.style.SUCCESS(f"Weekly matches sent to {sent} member(s)."))
