from django.conf import settings


def _has_resume(request):
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated):
        return False
    from accounts.models import UserResume
    return UserResume.objects.filter(user=user).exists()


def feature_flags(request):
    """Expose toggles templates need (e.g. whether to show the Google button)."""
    return {
        'google_oauth_enabled': getattr(settings, 'GOOGLE_OAUTH_ENABLED', False),
        'posthog_key': getattr(settings, 'POSTHOG_KEY', ''),
        'posthog_host': getattr(settings, 'POSTHOG_HOST', ''),
        # One-shot: set by the user_signed_up signal, fired once as signup_completed.
        'has_saved_resume': _has_resume(request),
        'just_signed_up': request.session.pop('mtj_signed_up', '') if hasattr(request, 'session') else '',
    }


def saved_job_ids(request):
    if request.user.is_authenticated:
        try:
            ids = set(request.user.userprofile.saved_jobs.values_list('id', flat=True))
            return {'saved_job_ids': ids}
        except Exception:
            return {'saved_job_ids': set()}
    return {'saved_job_ids': set()}


# The most useful missing profile field first: stack and location drive matching.
_PROFILE_NEXT_STEP = (
    ("stack", "add the platforms you work with so we can match you to the right roles"),
    ("location", "add where you want to work so you only see roles you're eligible for"),
    ("name", "add your name"),
    ("linkedin", "add your LinkedIn so employers can check your experience"),
    ("bio", "add a one-line bio"),
)


def profile_nudge(request):
    """Top-of-page banner for signed-in members whose profile is incomplete.

    Uses UserProfile.profile_complete_pct() so it always agrees with the
    dashboard's 'Profile Complete' number. Not shown on account pages."""
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated) or request.path.startswith(("/accounts/", "/admin", "/staff")):
        return {}
    try:
        profile = user.userprofile
        pct = profile.profile_complete_pct()
    except Exception:
        return {}
    if pct >= 100:
        return {}
    have = {
        "stack": profile.preferred_stack.exists(),
        "location": bool(profile.preferred_location),
        "name": bool(user.first_name),
        "linkedin": bool(profile.linkedin_url),
        "bio": bool(profile.bio),
    }
    step = next(text for key, text in _PROFILE_NEXT_STEP if not have[key])
    return {"profile_nudge": {"pct": pct, "next": step}}
