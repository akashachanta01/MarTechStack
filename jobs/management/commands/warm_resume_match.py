from django.core.management.base import BaseCommand

from jobs.resume_match import job_requirements, _REQS_CACHE_KEY


class Command(BaseCommand):
    help = "Precompute every live job's required MarTech terms for Resume Match (off the request path)."

    def handle(self, *args, **options):
        from django.core.cache import cache
        cache.delete(_REQS_CACHE_KEY)  # rebuild from today's live jobs
        reqs, complete = job_requirements(budget_s=None)
        self.stdout.write(f"Resume Match: {len(reqs)} jobs analysed (complete={complete}).")
