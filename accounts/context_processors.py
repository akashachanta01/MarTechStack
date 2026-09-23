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
