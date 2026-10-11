"""Numbers for the admin home ("Today") page. Small, indexed counts only, so the
page stays fast; everything degrades to 0 instead of breaking the admin."""
from datetime import timedelta

from django import template
from django.contrib.auth import get_user_model
from django.utils import timezone

register = template.Library()


def _safe(fn, default=0):
    try:
        return fn()
    except Exception:
        return default


@register.simple_tag
def admin_kpis():
    from jobs.models import Job, Subscriber, CourseInterest, SponsorInquiry, CompanySource, SavedSearch
    from accounts.models import UserResume, UserProfile

    now = timezone.now()
    week = now - timedelta(days=7)
    day = now - timedelta(days=1)
    User = get_user_model()
    live = Job.objects.filter(is_active=True, screening_status="approved")
    people = User.objects.filter(is_staff=False)

    k = {
        "live_jobs": _safe(live.count),
        "live_companies": _safe(lambda: live.values("company").distinct().count()),
        "jobs_added_week": _safe(lambda: live.filter(created_at__gte=week).count()),
        "pending_review": _safe(lambda: Job.objects.filter(screening_status="pending").count()),
        "accounts": _safe(people.count),
        "accounts_week": _safe(lambda: people.filter(date_joined__gte=week).count()),
        "accounts_today": _safe(lambda: people.filter(date_joined__gte=day).count()),
        "subscribers": _safe(lambda: Subscriber.objects.filter(is_active=True).count()),
        "subscribers_week": _safe(lambda: Subscriber.objects.filter(is_active=True, created_at__gte=week).count()),
        "resumes": _safe(UserResume.objects.count),
        "waitlist": _safe(lambda: UserProfile.objects.filter(pro_waitlist=True).count()),
        "alerts": _safe(lambda: SavedSearch.objects.filter(is_active=True).count()),
        "course_open": _safe(lambda: CourseInterest.objects.filter(handled=False).count()),
        "course_total": _safe(CourseInterest.objects.count),
        "sponsor_open": _safe(lambda: SponsorInquiry.objects.filter(handled=False).count()),
        "sources_enabled": _safe(lambda: CompanySource.objects.filter(enabled=True).count()),
        "sources_quiet": _safe(lambda: CompanySource.objects.filter(enabled=True, consecutive_empty__gte=7).count()),
        "recent_people": _safe(lambda: list(people.order_by("-date_joined")[:6]), []),
        "recent_courses": _safe(lambda: list(CourseInterest.objects.filter(handled=False).select_related("course").order_by("-created_at")[:5]), []),
        "recent_sponsors": _safe(lambda: list(SponsorInquiry.objects.filter(handled=False).order_by("-created_at")[:5]), []),
    }
    k["attention"] = k["pending_review"] + k["course_open"] + k["sponsor_open"]
    return k
