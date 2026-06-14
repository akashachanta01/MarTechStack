from django.conf import settings


def feature_flags(request):
    """Expose toggles templates need (e.g. whether to show the Google button)."""
    return {'google_oauth_enabled': getattr(settings, 'GOOGLE_OAUTH_ENABLED', False)}


def saved_job_ids(request):
    if request.user.is_authenticated:
        try:
            ids = set(request.user.userprofile.saved_jobs.values_list('id', flat=True))
            return {'saved_job_ids': ids}
        except Exception:
            return {'saved_job_ids': set()}
    return {'saved_job_ids': set()}
