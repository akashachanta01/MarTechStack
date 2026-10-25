"""Automatic checks for jobs that recruiters submit through /post-job/.

Founder asked (Oct 25 2026): verified submissions go live on their own, and an
email confirms every one, so no posting is ever missed. A submission is posted
automatically only when all checks pass; anything doubtful stays in review and
the founder gets an email saying exactly why.
"""
import logging
import threading
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)

MIN_DESCRIPTION_CHARS = 200
MIN_SCREEN_SCORE = 70


def _root(host):
    return ".".join((host or "").lower().split(".")[-2:])


def check_submission(job):
    """(passed, checks): checks is a list of (ok, plain-English line) for the email."""
    from jobs.management.commands.recheck_pending import posting_status, OPEN, CLOSED
    from jobs.models import Job, poster_email_check
    from jobs.screener import MarTechScreener

    checks = []

    # 1. Is it a MarTech role? Same screener every ingested job goes through.
    try:
        res = MarTechScreener().screen(job.title, job.company, job.location, job.description or "", job.apply_url)
    except Exception as e:  # pragma: no cover - defensive
        logger.warning("Submission screen failed for %s: %s", job.pk, e)
        res = {"status": "pending", "score": 0, "reason": "screening unavailable"}
    relevant = res.get("status") == "approved" and float(res.get("score") or 0) >= MIN_SCREEN_SCORE
    checks.append((relevant, "MarTech role: yes" if relevant else f"MarTech role: not confirmed ({res.get('reason', '')[:120]})"))

    # 2. Is it really this employer's job? Either the company's careers system
    # confirms the posting is open, or the poster's work email matches the apply link.
    ats = posting_status(job.apply_url, timeout=6)
    email_check = poster_email_check(job.poster_email, job.apply_url)
    if ats == CLOSED:
        checks.append((False, "Apply link: the company's careers site says this posting is closed"))
    elif ats == OPEN:
        checks.append((True, "Apply link: confirmed open on the company's careers site"))
    elif email_check == "match":
        checks.append((True, "Apply link: the poster's work email matches the apply link's company"))
    else:
        why = {"personal": "a personal email (Gmail etc.)", "different": "an email from a different domain"}.get(
            email_check, "no email")
        checks.append((False, f"Apply link: couldn't confirm it's the employer's job (careers site not readable, poster used {why})"))

    # 3. Enough detail to be useful (and not a spam stub).
    desc_ok = len((job.description or "").strip()) >= MIN_DESCRIPTION_CHARS
    checks.append((desc_ok, "Description: complete" if desc_ok else "Description: too short to publish"))

    # 4. Not already listed (same company + title + location).
    dupe = (Job.objects.filter(is_active=True, screening_status="approved", company__iexact=job.company,
                               title__iexact=job.title, location__iexact=job.location).exclude(pk=job.pk).exists())
    checks.append((not dupe, "Duplicate: none" if not dupe else "Duplicate: the same role is already live"))

    job._screen_result = res
    return all(ok for ok, _ in checks), checks


def process_submission(job_id):
    """Check one submission; publish it if every check passes; email the founder
    either way (and the poster when it goes live). Never raises."""
    from jobs.models import Job
    from jobs.emails import send_submission_result_emails
    try:
        job = Job.objects.get(pk=job_id)
        passed, checks = check_submission(job)
        res = getattr(job, "_screen_result", {}) or {}
        details = dict(job.screening_details or {})
        details["auto_check"] = {"passed": passed, "checks": [line for _, line in checks],
                                 "at": timezone.now().isoformat()}
        fields = {"screening_details": details, "screening_score": res.get("score") or job.screening_score,
                  "screened_at": timezone.now()}
        if passed:
            fn = ((res.get("details") or {}).get("signals") or {}).get("function")
            fields.update(screening_status="approved", is_active=True, went_live_at=timezone.now(),
                          screening_reason="Auto-verified submission: " + "; ".join(line for _, line in checks))
            if fn and job.function in ("", None, "other"):
                fields["function"] = fn
        else:
            fields["screening_reason"] = "Needs review: " + "; ".join(line for ok, line in checks if not ok)
        Job.objects.filter(pk=job.pk).update(**fields)
        job.refresh_from_db()
        if passed:
            cache.delete("popular_tech_stacks_v4")
            cache.delete("available_countries_v4")
        send_submission_result_emails(job, passed, checks)
    except Exception:
        logger.exception("Processing submission %s failed", job_id)
        # Never let a submission vanish silently: fall back to the plain review alert.
        try:
            from jobs.emails import send_admin_new_job_submission_alert
            send_admin_new_job_submission_alert(Job.objects.get(pk=job_id))
        except Exception:
            pass


def process_submission_async(job_id):
    """Run the checks off the request thread (the screener can take ~10s; Render
    kills requests at 30s). Tests run it inline."""
    if getattr(settings, "SUBMISSION_CHECKS_INLINE", False):
        return process_submission(job_id)
    def run():
        from django.db import connection
        try:
            process_submission(job_id)
        finally:
            connection.close()  # a thread's DB connection is never reused by Django
    threading.Thread(target=run, daemon=True).start()
