def saved_job_ids(request):
    if request.user.is_authenticated:
        try:
            ids = set(request.user.userprofile.saved_jobs.values_list('id', flat=True))
            return {'saved_job_ids': ids}
        except Exception:
            return {'saved_job_ids': set()}
    return {'saved_job_ids': set()}
